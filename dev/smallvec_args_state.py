from pathlib import Path

EMPTY = "_ARGUMENT_CACHE_EMPTY"
PUBLISHING = "_ARGUMENT_CACHE_PUBLISHING"
READY = "_ARGUMENT_CACHE_READY"

small = Path("src/small_array.jl")
text = small.read_text()
old = '''mutable struct SmallVec{T, V <: AbstractVector{T}} <: AbstractVector{T}\n    data::Union{Backing{T}, V}\n'''
new = '''mutable struct SmallVec{T, V <: AbstractVector{T}} <: AbstractVector{T}\n    data::Union{Backing{T}, V}\n    @atomic publication_state::UInt8\n'''
assert text.count(old) == 1
text = text.replace(old, new)

# Every inner constructor initializes the inline publication byte to zero.
repls = [
    ('new{T, V}(Backing{T}(x...))', 'new{T, V}(Backing{T}(x...), UInt8(0))'),
    ('new{T, V}(x)', 'new{T, V}(x, UInt8(0))'),
    ('new{T, V}(Backing{T}())', 'new{T, V}(Backing{T}(), UInt8(0))'),
    ('new{T, V}(Backing{T}(x...))', 'new{T, V}(Backing{T}(x...), UInt8(0))'),
    ('new{T, V}(V(x isa Tuple ? collect(x) : x))', 'new{T, V}(V(x isa Tuple ? collect(x) : x), UInt8(0))'),
    ('return new{T, V}(inner)', 'return new{T, V}(inner, UInt8(0))'),
]
for old, new in repls:
    if old in text:
        text = text.replace(old, new)
small.write_text(text)

term = Path("src/terminterface.jl")
text = term.read_text()
marker = '"""\n    arguments(expr)\n'
assert text.count(marker) == 1
helpers = r'''const _ARGUMENT_CACHE_EMPTY = UInt8(0)
const _ARGUMENT_CACHE_PUBLISHING = UInt8(1)
const _ARGUMENT_CACHE_READY = UInt8(2)

@inline function _argument_cache_ready(args::ArgsT)
    state = @atomic :acquire args.publication_state
    state == _ARGUMENT_CACHE_READY && return true
    if state == _ARGUMENT_CACHE_PUBLISHING
        while (@atomic :acquire args.publication_state) != _ARGUMENT_CACHE_READY
            yield()
        end
        return true
    end
    # Preserve low-level callers that explicitly construct a cache-bearing node
    # with a pre-populated `args` vector.
    if !isempty(args)
        @atomic :release args.publication_state = _ARGUMENT_CACHE_READY
        return true
    end
    return false
end

@inline function _publish_argument_cache!(args::ArgsT{T}, candidate::ArgsT{T}) where {T}
    result = @atomicreplace :acquire_release :acquire args.publication_state \
        _ARGUMENT_CACHE_EMPTY => _ARGUMENT_CACHE_PUBLISHING
    if result.success
        args.data = candidate.data
        @atomic :release args.publication_state = _ARGUMENT_CACHE_READY
    else
        while (@atomic :acquire args.publication_state) != _ARGUMENT_CACHE_READY
            yield()
        end
    end
    return args
end

function _materialize_addmul_arguments!(
    args::ArgsT{T}, coeff, dict, variant, shape, type
) where {T}
    _argument_cache_ready(args) && return args
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
    return _publish_argument_cache!(args, candidate)
end

function _materialize_arrayop_arguments!(
    args::ArgsT{T}, output_idx, expr, reduce, term, ranges
) where {T}
    _argument_cache_ready(args) && return args
    candidate = ArgsT{T}()
    push!(candidate, Const{T}(output_idx))
    push!(candidate, Const{T}(expr))
    push!(candidate, Const{T}(reduce))
    push!(candidate, Const{T}(term))
    push!(candidate, Const{T}(ranges))
    return _publish_argument_cache!(args, candidate)
end

function _materialize_arraymaker_arguments!(args::ArgsT{T}, regions, values) where {T}
    _argument_cache_ready(args) && return args
    candidate = ArgsT{T}()
    push!(candidate, BSImpl.Const{T}(regions))
    push!(candidate, BSImpl.Const{T}(values))
    return _publish_argument_cache!(args, candidate)
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
        BSImpl.AddMul(; coeff, dict, variant, args, shape, type) => begin
            _materialize_addmul_arguments!(args, coeff, dict, variant, shape, type)
            return ROArgsT{T}(args)
        end
        BSImpl.Div(num, den) => ROArgsT{T}(ArgsT{T}((num, den)))
        BSImpl.ArrayOp(; output_idx, expr, reduce, term, ranges, args) => begin
            if term === nothing
                _materialize_arrayop_arguments!(args, output_idx, expr, reduce, term, ranges)
                return ROArgsT{T}(args)
            elseif term isa BasicSymbolic{T}
                return arguments(term)
            end
        end
        BSImpl.ArrayMaker(; regions, values, args) => begin
            _materialize_arraymaker_arguments!(args, regions, values)
            return ROArgsT{T}(args)
        end
    end
end'''
text = text[:start] + replacement + text[end:]
term.write_text(text)
