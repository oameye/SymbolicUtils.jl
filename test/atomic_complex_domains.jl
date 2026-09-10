using Test
using SymbolicUtils

@testset "raw atomic complex domain semantics" begin
    @syms x::Real z::Complex{Real} n::Number m::Number

    @test conj(x) === x
    @test real(x) === x
    @test SymbolicUtils._iszero(imag(x))

    cz = conj(z)
    @test !isequal(cz, z)
    @test operation(cz) === conj
    @test SymbolicUtils.symtype(cz) == SymbolicUtils.symtype(z)
    @test SymbolicUtils.symtype(real(z)) <: Real
    @test SymbolicUtils.symtype(imag(z)) <: Real

    cn = conj(n)
    @test !isequal(cn, n)
    @test operation(cn) === conj
    @test SymbolicUtils.symtype(cn) == Number

    @test operation(exp(z)) === exp
    @test operation(sin(z)) === sin
    @test operation(cos(z)) === cos
    @test operation(log(z)) === log
    @test operation(sqrt(z)) === sqrt

    phase = exp(im * x)
    @test operation(phase) === exp
    @test Set(SymbolicUtils.search_variables(phase)) == Set([x])

    # Establish what the scalar eltype test in `conj` actually means. Numeric scalar
    # types are their own `eltype`; `Complex{Real}` is not misclassified as Real.
    @test eltype(Complex{Real}) == Complex{Real}

    @testset "real-valued projections are stable under rebuild" begin
        rn = real(n)
        in_ = imag(n)
        @test SymbolicUtils.symtype(rn) <: Real
        @test SymbolicUtils.symtype(in_) <: Real

        # Substitution rebuilds the Term through TermInterface/maketerm. Its inferred
        # symtype must agree with the direct constructor rather than widening back to Number.
        rn2 = substitute(rn, Dict(n => m))
        in2 = substitute(in_, Dict(n => m))
        @test SymbolicUtils.symtype(rn2) <: Real
        @test SymbolicUtils.symtype(in2) <: Real
        @test operation(rn2) === real
        @test operation(in2) === imag
    end

    @testset "magnitudes are real-valued" begin
        for v in (z, n)
            @test SymbolicUtils.symtype(abs(v)) <: Real
            @test SymbolicUtils.symtype(abs2(v)) <: Real
        end
    end
end
