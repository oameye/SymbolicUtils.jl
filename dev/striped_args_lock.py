from pathlib import Path

path = Path("src/terminterface.jl")
text = path.read_text()

marker = '"""\n    arguments(expr)\n'
assert text.count(marker) == 1
helpers = r'''const _ARGUMENT_CACHE_LOCKS = ntuple(_ -> Threads.SpinLock(), 64)

@inline function _argument_cache_lock(args::ArgsT)
    idx = Int(mod(objectid(args), UInt(length(_ARGUMENT_CACHE_LOCKS)))) + 1
    return @inbounds _ARGUMENT_CACHE_LOCKS[idx]
end

@inline function _argument_cache_ready(args::ArgsT)
    lk = _argument_cache_lock(args)
    lock(lk)
    try
        return !isempty(args)
    finally
        unlock(lk)
    end
end

@inline function _publish_argument_cache!(args::ArgsT{T}, candidate::ArgsT{T}) where {T}
    lk = _argument_cache_lock(args)
    lock(lk)
    try
        if isempty(args)
            # Preserve the existing `args` object and its public/internal field type.
            # Only replace its private backing after the candidate is complete.
            args.data = candidate.data
        end
        return args
    finally
        unlock(lk)
    end
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
path.write_text(text)
