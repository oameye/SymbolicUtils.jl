from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


types = Path("src/types.jl")
s = types.read_text()

s = replace_once(
    s,
    'const SmallV{T} = SmallVec{T, Vector{T}}\n',
    '''const SmallV{T} = SmallVec{T, Vector{T}}\n\n# Lazy derived data on hash-consed symbolic nodes must be published atomically.\n# A cache slot replaces the eagerly allocated empty SmallVec previously stored on\n# every cache-bearing node; the complete SmallVec is allocated only on first use.\nmutable struct ArgumentCache{T}\n    @atomic value::Union{Nothing, T}\n    ArgumentCache{T}() where {T} = new{T}(nothing)\nend\n''',
    "insert ArgumentCache",
)

# Change only the cache-bearing variants, leaving Term.args as an ordinary SmallVec.
for label, old, new in [
    (
        "AddMul args",
        '''        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        hash::UInt\n        hash2::UInt\n        id::IdentT\n    end\n    struct Div''',
        '''        const type::TypeT\n        const args::ArgumentCache{SmallV{BasicSymbolicImpl.Type{T}}}\n        hash::UInt\n        hash2::UInt\n        id::IdentT\n    end\n    struct Div''',
    ),
    (
        "ArrayOp args",
        '''        const ranges::Dict{BasicSymbolicImpl.Type{T}, StepRange{Int, Int}}\n        const metadata::MetadataT\n        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        hash::UInt''',
        '''        const ranges::Dict{BasicSymbolicImpl.Type{T}, StepRange{Int, Int}}\n        const metadata::MetadataT\n        const shape::ShapeT\n        const type::TypeT\n        const args::ArgumentCache{SmallV{BasicSymbolicImpl.Type{T}}}\n        hash::UInt''',
    ),
    (
        "ArrayMaker args",
        '''        const metadata::MetadataT\n        # _has_ to be an array shape.\n        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        hash::UInt''',
        '''        const metadata::MetadataT\n        # _has_ to be an array shape.\n        const shape::ShapeT\n        const type::TypeT\n        const args::ArgumentCache{SmallV{BasicSymbolicImpl.Type{T}}}\n        hash::UInt''',
    ),
]:
    s = replace_once(s, old, new, label)

s = replace_once(
    s,
    'const ArgsT{T} = SmallV{BasicSymbolic{T}}\n',
    '''const ArgsT{T} = SmallV{BasicSymbolic{T}}\nconst ArgsCacheT{T} = ArgumentCache{ArgsT{T}}\n''',
    "ArgsCacheT alias",
)

s = s.replace(
    'ordered_override_properties(::Type{BSImpl.AddMul{T}}) where {T} = (ArgsT{T}(), 0, 0, nothing)',
    'ordered_override_properties(::Type{BSImpl.AddMul{T}}) where {T} = (ArgsCacheT{T}(), 0, 0, nothing)',
)
s = s.replace(
    'ordered_override_properties(::Type{<:BSImpl.ArrayOp{T}}) where {T} = (ArgsT{T}(), 0, 0, nothing)',
    'ordered_override_properties(::Type{<:BSImpl.ArrayOp{T}}) where {T} = (ArgsCacheT{T}(), 0, 0, nothing)',
)
s = s.replace(
    'ordered_override_properties(::Type{<:BSImpl.ArrayMaker{T}}) where {T} = (ArgsT{T}(), 0, 0, nothing)',
    'ordered_override_properties(::Type{<:BSImpl.ArrayMaker{T}}) where {T} = (ArgsCacheT{T}(), 0, 0, nothing)',
)

# setproperties deliberately invalidates derived caches.
s = replace_once(
    s,
    '''                             get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                             ArgsT{T}(), Z, Z, nothing)\n        BSImpl.Div''',
    '''                             get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                             ArgsCacheT{T}(), Z, Z, nothing)\n        BSImpl.Div''',
    "setproperties AddMul",
)
s = replace_once(
    s,
    '''                              get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                              ArgsT{T}(), Z, Z, nothing)\n        BSImpl.ArrayMaker''',
    '''                              get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                              ArgsCacheT{T}(), Z, Z, nothing)\n        BSImpl.ArrayMaker''',
    "setproperties ArrayOp",
)
s = replace_once(
    s,
    '''                                 get(p, :metadata, metadata), get(p, :shape, shape),\n                                 get(p, :type, type), ArgsT{T}(), Z, Z, nothing)''',
    '''                                 get(p, :metadata, metadata), get(p, :shape, shape),\n                                 get(p, :type, type), ArgsCacheT{T}(), Z, Z, nothing)''',
    "setproperties ArrayMaker",
)

types.write_text(s)


term = Path("src/terminterface.jl")
s = term.read_text()

marker = '''function TermInterface.arguments(x::BSImpl.Type{T})::ROArgsT{T} where {T}\n'''
helpers = '''@inline function _get_cached_arguments(cache::ArgsCacheT{T}) where {T}\n    return @atomic :acquire cache.value\nend\n\n@inline function _publish_cached_arguments!(cache::ArgsCacheT{T}, candidate::ArgsT{T}) where {T}\n    result = @atomicreplace :acquire_release :acquire cache.value nothing => candidate\n    return result.success ? candidate : result.old::ArgsT{T}\nend\n\n'''
s = replace_once(s, marker, helpers + marker, "cache helpers")

old_addmul = '''        BSImpl.AddMul(; coeff, dict, variant, args, shape, type) => begin\n            isempty(args) || return ROArgsT{T}(args)\n            @match variant begin\n                AddMulVariant.ADD => begin\n                    if !iszero(coeff)\n                        push!(args, Const{T}(coeff))\n                    end\n                    for (k, v) in dict\n                        newterm = @match k begin\n                            BSImpl.AddMul(; dict = d2, variant = v2, type, shape, metadata) && if v2 == AddMulVariant.MUL end => begin\n                                Mul{T}(v, d2; shape, type, metadata)\n                            end\n                            _ => Mul{T}(v, ACDict{T}(k => 1); shape, type)\n                        end\n                        push!(args, newterm)\n                    end\n                end\n                AddMulVariant.MUL => begin\n                    if !_isone(coeff)\n                        push!(args, Const{T}(coeff))\n                    end\n                    for (k, v) in dict\n                        push!(args, k ^ v)\n                    end\n                end\n            end\n            return ROArgsT{T}(args)\n        end\n'''
new_addmul = '''        BSImpl.AddMul(; coeff, dict, variant, args, shape, type) => begin\n            cached = _get_cached_arguments(args)\n            cached === nothing || return ROArgsT{T}(cached)\n\n            newargs = ArgsT{T}()\n            @match variant begin\n                AddMulVariant.ADD => begin\n                    if !iszero(coeff)\n                        push!(newargs, Const{T}(coeff))\n                    end\n                    for (k, v) in dict\n                        newterm = @match k begin\n                            BSImpl.AddMul(; dict = d2, variant = v2, type, shape, metadata) && if v2 == AddMulVariant.MUL end => begin\n                                Mul{T}(v, d2; shape, type, metadata)\n                            end\n                            _ => Mul{T}(v, ACDict{T}(k => 1); shape, type)\n                        end\n                        push!(newargs, newterm)\n                    end\n                end\n                AddMulVariant.MUL => begin\n                    if !_isone(coeff)\n                        push!(newargs, Const{T}(coeff))\n                    end\n                    for (k, v) in dict\n                        push!(newargs, k ^ v)\n                    end\n                end\n            end\n            return ROArgsT{T}(_publish_cached_arguments!(args, newargs))\n        end\n'''
s = replace_once(s, old_addmul, new_addmul, "AddMul arguments")

old_arrayop = '''        BSImpl.ArrayOp(; output_idx, expr, reduce, term, ranges, shape, type, args) => begin\n            if term === nothing\n                isempty(args) || return ROArgsT{T}(args)\n                push!(args, Const{T}(output_idx))\n                push!(args, Const{T}(expr))\n                push!(args, Const{T}(reduce))\n                push!(args, Const{T}(term))\n                push!(args, Const{T}(ranges))\n                return ROArgsT{T}(args)\n            elseif term isa BasicSymbolic{T}\n                return arguments(term)\n            end\n        end\n'''
new_arrayop = '''        BSImpl.ArrayOp(; output_idx, expr, reduce, term, ranges, shape, type, args) => begin\n            if term === nothing\n                cached = _get_cached_arguments(args)\n                cached === nothing || return ROArgsT{T}(cached)\n\n                newargs = ArgsT{T}()\n                push!(newargs, Const{T}(output_idx))\n                push!(newargs, Const{T}(expr))\n                push!(newargs, Const{T}(reduce))\n                push!(newargs, Const{T}(term))\n                push!(newargs, Const{T}(ranges))\n                return ROArgsT{T}(_publish_cached_arguments!(args, newargs))\n            elseif term isa BasicSymbolic{T}\n                return arguments(term)\n            end\n        end\n'''
s = replace_once(s, old_arrayop, new_arrayop, "ArrayOp arguments")

old_arraymaker = '''        BSImpl.ArrayMaker(; regions, values, args) => begin\n            isempty(args) || return ROArgsT{T}(args)\n            push!(args, BSImpl.Const{T}(regions))\n            push!(args, BSImpl.Const{T}(values))\n            return ROArgsT{T}(args)\n        end\n'''
new_arraymaker = '''        BSImpl.ArrayMaker(; regions, values, args) => begin\n            cached = _get_cached_arguments(args)\n            cached === nothing || return ROArgsT{T}(cached)\n\n            newargs = ArgsT{T}()\n            push!(newargs, BSImpl.Const{T}(regions))\n            push!(newargs, BSImpl.Const{T}(values))\n            return ROArgsT{T}(_publish_cached_arguments!(args, newargs))\n        end\n'''
s = replace_once(s, old_arraymaker, new_arraymaker, "ArrayMaker arguments")
term.write_text(s)


runtests = Path("test/runtests.jl")
s = runtests.read_text()
s = replace_once(
    s,
    '            @safetestset "Basics" begin include("basics.jl") end\n',
    '            @safetestset "Basics" begin include("basics.jl") end\n            @safetestset "Thread-safe arguments" begin include("threadsafe_arguments.jl") end\n',
    "runtests include",
)
runtests.write_text(s)

Path("test/threadsafe_arguments.jl").write_text(r'''using Test
using SymbolicUtils
using SymbolicUtils: SymReal
using TermInterface
using Base.Threads

function fresh_sum(trial; nargs = 1024)
    xs = [
        SymbolicUtils.Sym{SymReal}(Symbol(:threadsafe_args_, trial, :_, i); type = Real)
        for i in 1:nargs
    ]
    return sum(xs)
end

@testset "lazy arguments cache publication" begin
    expr = fresh_sum(0; nargs = 32)
    first_args = arguments(expr)
    second_args = arguments(expr)
    @test isequal(collect(first_args), collect(second_args))
    @test parent(first_args) === parent(second_args)
end

@testset "concurrent first arguments access" begin
    if nthreads() == 1 && get(ENV, "SYMBOLICUTILS_ARGUMENTS_SUBPROCESS", "0") != "1"
        script = @__FILE__
        project = dirname(@__DIR__)
        cmd = addenv(
            `$(Base.julia_cmd()) --project=$project --threads=4 $script`,
            "SYMBOLICUTILS_ARGUMENTS_SUBPROCESS" => "1",
        )
        @test success(cmd)
    else
        @test nthreads() > 1
        for trial in 1:25
            expr = fresh_sum(trial)
            expected = Set(keys(expr.dict))
            ready = Atomic{Int}(0)
            go = Atomic{Bool}(false)
            ntasks = max(8, 4 * nthreads())
            tasks = [
                @spawn begin
                    atomic_add!(ready, 1)
                    while !go[]
                        yield()
                    end
                    collect(arguments(expr))
                end for _ in 1:ntasks
            ]
            while ready[] < ntasks
                yield()
            end
            go[] = true
            results = fetch.(tasks)
            @test all(length(args) == length(expected) for args in results)
            @test all(isequal(Set(args), expected) for args in results)
        end
    end
end
''')

print("thread-safe argument-cache transformation applied")
