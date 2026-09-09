from pathlib import Path

types = Path("src/types.jl")
text = types.read_text()

anchor = 'const SmallV{T} = SmallVec{T, Vector{T}}\n'
assert text.count(anchor) == 1
text = text.replace(anchor, anchor + '''\nconst _ARGUMENT_CACHE_EMPTY = UInt8(0)\nconst _ARGUMENT_CACHE_PUBLISHING = UInt8(1)\nconst _ARGUMENT_CACHE_READY = UInt8(2)\nmutable struct ArgumentCacheState\n    @atomic value::UInt8\n    ArgumentCacheState() = new(_ARGUMENT_CACHE_EMPTY)\nend\n@inline _new_argument_cache_state() = ArgumentCacheState()\n''')

old = '''        const variant::AddMulVariant.T\n        const metadata::MetadataT\n        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        hash::UInt\n'''
new = '''        const variant::AddMulVariant.T\n        const metadata::MetadataT\n        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        const args_state::ArgumentCacheState\n        hash::UInt\n'''
assert text.count(old) == 1
text = text.replace(old, new)

old = '''        const ranges::Dict{BasicSymbolicImpl.Type{T}, StepRange{Int, Int}}\n        const metadata::MetadataT\n        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        hash::UInt\n'''
new = '''        const ranges::Dict{BasicSymbolicImpl.Type{T}, StepRange{Int, Int}}\n        const metadata::MetadataT\n        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        const args_state::ArgumentCacheState\n        hash::UInt\n'''
assert text.count(old) == 1
text = text.replace(old, new)

old = '''        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        hash::UInt\n        hash2::UInt\n        id::IdentT\n    end\nend\n'''
new = '''        const shape::ShapeT\n        const type::TypeT\n        const args::SmallV{BasicSymbolicImpl.Type{T}}\n        const args_state::ArgumentCacheState\n        hash::UInt\n        hash2::UInt\n        id::IdentT\n    end\nend\n'''
assert text.count(old) == 1
text = text.replace(old, new)

for old, new in [
    ('ordered_override_properties(::Type{BSImpl.AddMul{T}}) where {T} = (ArgsT{T}(), 0, 0, nothing)\n',
     'ordered_override_properties(::Type{BSImpl.AddMul{T}}) where {T} = (ArgsT{T}(), _new_argument_cache_state(), 0, 0, nothing)\n'),
    ('ordered_override_properties(::Type{<:BSImpl.ArrayOp{T}}) where {T} = (ArgsT{T}(), 0, 0, nothing)\n',
     'ordered_override_properties(::Type{<:BSImpl.ArrayOp{T}}) where {T} = (ArgsT{T}(), _new_argument_cache_state(), 0, 0, nothing)\n'),
    ('ordered_override_properties(::Type{<:BSImpl.ArrayMaker{T}}) where {T} = (ArgsT{T}(), 0, 0, nothing)\n',
     'ordered_override_properties(::Type{<:BSImpl.ArrayMaker{T}}) where {T} = (ArgsT{T}(), _new_argument_cache_state(), 0, 0, nothing)\n'),
]:
    assert text.count(old) == 1
    text = text.replace(old, new)

old = '''        BSImpl.AddMul(; coeff, dict, variant, metadata, shape, type) =>\n            BSImpl.AddMul{T}(get(p, :coeff, coeff), get(p, :dict, dict), get(p, :variant, variant),\n                             get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                             ArgsT{T}(), Z, Z, nothing)\n'''
new = '''        BSImpl.AddMul(; coeff, dict, variant, metadata, shape, type) =>\n            BSImpl.AddMul{T}(get(p, :coeff, coeff), get(p, :dict, dict), get(p, :variant, variant),\n                             get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                             ArgsT{T}(), _new_argument_cache_state(), Z, Z, nothing)\n'''
assert text.count(old) == 1
text = text.replace(old, new)

old = '''        BSImpl.ArrayOp(; output_idx, expr, reduce, term, ranges, metadata, shape, type) =>\n            BSImpl.ArrayOp{T}(get(p, :output_idx, output_idx), get(p, :expr, expr),\n                              get(p, :reduce, reduce), get(p, :term, term), get(p, :ranges, ranges),\n                              get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                              ArgsT{T}(), Z, Z, nothing)\n'''
new = '''        BSImpl.ArrayOp(; output_idx, expr, reduce, term, ranges, metadata, shape, type) =>\n            BSImpl.ArrayOp{T}(get(p, :output_idx, output_idx), get(p, :expr, expr),\n                              get(p, :reduce, reduce), get(p, :term, term), get(p, :ranges, ranges),\n                              get(p, :metadata, metadata), get(p, :shape, shape), get(p, :type, type),\n                              ArgsT{T}(), _new_argument_cache_state(), Z, Z, nothing)\n'''
assert text.count(old) == 1
text = text.replace(old, new)

old = '''        BSImpl.ArrayMaker(; regions, values, metadata, shape, type) =>\n            BSImpl.ArrayMaker{T}(get(p, :regions, regions), get(p, :values, values),\n                                 get(p, :metadata, metadata), get(p, :shape, shape),\n                                 get(p, :type, type), ArgsT{T}(), Z, Z, nothing)\n'''
new = '''        BSImpl.ArrayMaker(; regions, values, metadata, shape, type) =>\n            BSImpl.ArrayMaker{T}(get(p, :regions, regions), get(p, :values, values),\n                                 get(p, :metadata, metadata), get(p, :shape, shape),\n                                 get(p, :type, type), ArgsT{T}(), _new_argument_cache_state(), Z, Z, nothing)\n'''
assert text.count(old) == 1
text = text.replace(old, new)

types.write_text(text)

term = Path("src/terminterface.jl")
text = term.read_text()
marker = '"""\n    arguments(expr)\n'
assert text.count(marker) == 1
helpers = r'''@inline function _argument_cache_ready(state::ArgumentCacheState)
    value = @atomic :acquire state.value
    value == _ARGUMENT_CACHE_READY && return true
    if value == _ARGUMENT_CACHE_PUBLISHING
        while (@atomic :acquire state.value) != _ARGUMENT_CACHE_READY
            yield()
        end
        return true
    end
    return false
end

@inline function _publish_argument_cache!(
    args::ArgsT{T}, state::ArgumentCacheState, candidate::ArgsT{T}
) where {T}
    result = @atomicreplace :acquire_release :acquire state.value _ARGUMENT_CACHE_EMPTY => _ARGUMENT_CACHE_PUBLISHING
    if result.success
        args.data = candidate.data
        @atomic :release state.value = _ARGUMENT_CACHE_READY
    else
        while (@atomic :acquire state.value) != _ARGUMENT_CACHE_READY
            yield()
        end
    end
    return args
end

function _materialize_addmul_arguments!(
    args::ArgsT{T}, state::ArgumentCacheState, coeff, dict, variant, shape, type
) where {T}
    _argument_cache_ready(state) && return args
    candidate = ArgsT{T}()
    @match variant begin
        AddMulVariant.ADD => begin
            if !iszero(coeff)
                push!(candidate, Const{T}(coeff))
            end
            for (k, v) in dict
                newterm = @match k begin
                    BSImpl.AddMul(; dict = d2, variant = v2, type, shape, metadata) && if v2 == AddMulVariant.MUL end => begin
                        Mul{T}(v, d2; shape, type, metadata)
                    end
                    _ => Mul{T}(v, ACDict{T}(k => 1); shape, type)
                end
                push!(candidate, newterm)
            end
        end
        AddMulVariant.MUL => begin
            if !_isone(coeff)
                push!(candidate, Const{T}(coeff))
            end
            for (k, v) in dict
                push!(candidate, k ^ v)
            end
        end
    end
    return _publish_argument_cache!(args, state, candidate)
end

function _materialize_arrayop_arguments!(
    args::ArgsT{T}, state::ArgumentCacheState, output_idx, expr, reduce, term, ranges
) where {T}
    _argument_cache_ready(state) && return args
    candidate = ArgsT{T}()
    push!(candidate, Const{T}(output_idx))
    push!(candidate, Const{T}(expr))
    push!(candidate, Const{T}(reduce))
    push!(candidate, Const{T}(term))
    push!(candidate, Const{T}(ranges))
    return _publish_argument_cache!(args, state, candidate)
end

function _materialize_arraymaker_arguments!(
    args::ArgsT{T}, state::ArgumentCacheState, regions, values
) where {T}
    _argument_cache_ready(state) && return args
    candidate = ArgsT{T}()
    push!(candidate, BSImpl.Const{T}(regions))
    push!(candidate, BSImpl.Const{T}(values))
    return _publish_argument_cache!(args, state, candidate)
end

'''
text = text.replace(marker, helpers + marker)

start = text.index('function TermInterface.arguments(x::BSImpl.Type{T})::ROArgsT{T} where {T}')
end_marker = '\nend\n\n"""\n    $TYPEDSIGNATURES'
end = text.index(end_marker, start) + len('\nend')
replacement = r'''function TermInterface.arguments(x::BSImpl.Type{T})::ROArgsT{T} where {T}
    @match x begin
        BSImpl.Const(_) => throw(ArgumentError("`Const` does not have arguments."))
        BSImpl.Sym(_) => throw(ArgumentError("`Sym` does not have arguments."))
        BSImpl.Term(; args) => ROArgsT{T}(args)
        BSImpl.AddMul(; coeff, dict, variant, args, args_state, shape, type) => begin
            _materialize_addmul_arguments!(args, args_state, coeff, dict, variant, shape, type)
            return ROArgsT{T}(args)
        end
        BSImpl.Div(num, den) => ROArgsT{T}(ArgsT{T}((num, den)))
        BSImpl.ArrayOp(; output_idx, expr, reduce, term, ranges, args, args_state) => begin
            if term === nothing
                _materialize_arrayop_arguments!(args, args_state, output_idx, expr, reduce, term, ranges)
                return ROArgsT{T}(args)
            elseif term isa BasicSymbolic{T}
                return arguments(term)
            end
        end
        BSImpl.ArrayMaker(; regions, values, args, args_state) => begin
            _materialize_arraymaker_arguments!(args, args_state, regions, values)
            return ROArgsT{T}(args)
        end
    end
end'''
text = text[:start] + replacement + text[end:]
term.write_text(text)
