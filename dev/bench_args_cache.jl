using SymbolicUtils
using SymbolicUtils: SymReal
using TermInterface
using Base.Threads
using Statistics

function syms_for(tag, n)
    [SymbolicUtils.Sym{SymReal}(Symbol(tag, :_, i); type = Real) for i in 1:n]
end
fresh_expr(tag; nargs = 32) = sum(syms_for(tag, nargs))

function median_elapsed(f; reps = 7)
    vals = Float64[]
    for _ in 1:reps
        GC.gc(); push!(vals, @elapsed f())
    end
    median(vals)
end

function bench_warm(; calls = 1_000_000)
    expr = fresh_expr(:warm; nargs = 32); arguments(expr)
    t = median_elapsed(; reps = 9) do
        for _ in 1:calls; arguments(expr); end
    end
    alloc = @allocated for _ in 1:calls; arguments(expr); end
    return 1e9 * t / calls, alloc
end
function bench_cold(; batch = 1000, nargs = 32)
    times = Float64[]; allocs = Int[]
    for rep in 1:7
        exprs = [fresh_expr(Symbol(:cold_time_, rep, :_, i); nargs) for i in 1:batch]
        GC.gc(); push!(times, @elapsed foreach(arguments, exprs))
        exprs = [fresh_expr(Symbol(:cold_alloc_, rep, :_, i); nargs) for i in 1:batch]
        push!(allocs, @allocated foreach(arguments, exprs))
    end
    return 1e6 * median(times) / batch, median(allocs) / batch
end
function bench_construct(; batch = 1000, nargs = 32)
    times = Float64[]; allocs = Int[]
    for rep in 1:7
        groups = [syms_for(Symbol(:construct_time_, rep, :_, b), nargs) for b in 1:batch]
        GC.gc(); push!(times, @elapsed map(sum, groups))
        groups = [syms_for(Symbol(:construct_alloc_, rep, :_, b), nargs) for b in 1:batch]
        push!(allocs, @allocated map(sum, groups))
    end
    return 1e6 * median(times) / batch, median(allocs) / batch
end
function stress(; trials = 50, nargs = 1024, ntasks = max(8, 4nthreads()))
    for trial in 1:trials
        expr = fresh_expr(Symbol(:stress_, trial); nargs)
        ready = Atomic{Int}(0); go = Atomic{Bool}(false)
        tasks = [@spawn begin
            atomic_add!(ready, 1); while !go[]; yield(); end; arguments(expr)
        end for _ in 1:ntasks]
        while ready[] < ntasks; yield(); end
        go[] = true
        results = fetch.(tasks); p = parent(first(results))
        @assert all(a -> parent(a) === p, results)
    end
    true
end
println("threads=", nthreads())
println("warm_ns_per_call, warm_alloc_bytes=", bench_warm())
println("cold_us_per_expr, cold_alloc_bytes_per_expr=", bench_cold())
println("construct_us_per_expr, construct_alloc_bytes_per_expr=", bench_construct())
println("stress=", stress())
