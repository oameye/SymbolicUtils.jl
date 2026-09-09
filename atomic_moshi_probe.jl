using Moshi.Data: @data

@data mutable Probe{T} begin
    struct Node
        @atomic value::Union{Nothing, T}
    end
end

x = Probe.Node{Vector{Int}}(nothing)
@assert (@atomic :acquire x.value) === nothing
candidate = [1, 2, 3]
result = @atomicreplace :release :monotonic x.value nothing => candidate
@assert result.success
@assert (@atomic :acquire x.value) === candidate
println("atomic Moshi field works")
