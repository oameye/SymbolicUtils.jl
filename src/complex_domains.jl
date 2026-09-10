# Domain propagation for scalar operations whose codomain is real even when the
# symbolic input domain permits complex values.
#
# `Base.real` and `Base.imag` already construct terms with `type = Real`, but generic
# term reconstruction consults `promote_symtype`.  Keep that reconstruction invariant
# consistent for an unconstrained numeric symbolic domain.
for f in (real, imag)
    @eval function promote_symtype(::typeof($f), T::TypeT)
        if T === Number
            return Real
        elseif T <: Complex
            return T.parameters[1]::TypeT
        else
            return T
        end
    end
end

# Magnitudes are real-valued for every scalar numeric domain.  In particular, a
# complex-valued symbolic scalar must not retain a complex symtype after `abs`/`abs2`.
for f in (abs, abs2)
    @eval promote_symtype(::typeof($f), ::TypeT) = Real
end
