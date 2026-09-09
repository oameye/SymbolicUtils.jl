using SymbolicUtils
using Base.Threads

function one_trial(trial; nargs = 4096, ntasks = max(8, 4 * nthreads()))
    xs = [SymbolicUtils.Sym{SymbolicUtils.SymReal}(Symbol(:x_, trial, :_, i); type = Real) for i in 1:nargs]
    expr = sum(xs)

    ready = Atomic{Int}(0)
    go = Atomic{Bool}(false)

    tasks = [
        @spawn begin
            atomic_add!(ready, 1)
            while !go[]
                yield()
            end
            arguments(expr)
        end for _ in 1:ntasks
    ]

    while ready[] < ntasks
        yield()
    end
    go[] = true

    foreach(fetch, tasks)
    return nothing
end

@assert nthreads() > 1

for trial in 1:200
    try
        one_trial(trial)
    catch err
        bt = catch_backtrace()
        msg = sprint(showerror, err, bt)
        println(stderr, msg)
        if occursin("ConcurrencyViolationError", msg)
            println("REPRODUCED on trial $trial with $(nthreads()) Julia threads")
            exit(0)
        end
        rethrow()
    end
end

error("race did not reproduce")
