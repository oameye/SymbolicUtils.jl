using Test
using SymbolicUtils

@testset "raw atomic complex domain semantics" begin
    @syms x::Real z::Complex{Real} n::Number

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
end
