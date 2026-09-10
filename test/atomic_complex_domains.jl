using Test
using SymbolicUtils

@testset "atomic complex domain semantics" begin
    @syms x::Real z::Complex n::Number

    @test conj(x) === x
    @test real(x) === x
    @test isequal(imag(x), 0)

    cz = conj(z)
    @test !isequal(cz, z)
    @test operation(cz) === conj
    @test symtype(cz) == symtype(z)
    @test symtype(real(z)) <: Real
    @test symtype(imag(z)) <: Real

    cn = conj(n)
    @test !isequal(cn, n)
    @test operation(cn) === conj
    @test symtype(cn) == Number

    @test operation(exp(z)) === exp
    @test operation(sin(z)) === sin
    @test operation(cos(z)) === cos
    @test operation(log(z)) === log
    @test operation(sqrt(z)) === sqrt

    @test operation(exp(im * x)) === exp
    @test search_variables(exp(im * x)) == Set([x]) || Set(search_variables(exp(im * x))) == Set([x])
end
