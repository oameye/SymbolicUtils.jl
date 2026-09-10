# Prototype domain correction for atomic complex symbolic scalars.
#
# A scalar is self-conjugate only when its symbolic type is known to be Real.
# Real-valued symbolic arrays are also self-conjugate elementwise. In particular,
# `Complex{Real}` is *not* real merely because `eltype(Complex{Real}) === Real`.
@inline function _is_provably_real_symtype(T::TypeT)
    T <: Real && return true
    T <: AbstractArray || return false
    return eltype(T) <: Real
end

for V in (SymReal, SafeReal, TreeReal)
    @eval function Base.conj(s::BasicSymbolic{$V})
        _is_provably_real_symtype(symtype(s)) && return s
        @match s begin
            BSImpl.Const(; val) => Const{$V}(conj(val))
            BSImpl.Term(; f, args, type, shape) && if f === complex && length(args) == 2 end => begin
                BSImpl.Term{$V}(f, ArgsT{$V}((args[1], -args[2])); type, shape)
            end
            _ => Term{$V}(conj, ArgsT{$V}((s,)); type = symtype(s), shape = shape(s))
        end
    end
end
