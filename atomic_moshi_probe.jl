using Moshi
using Moshi.Data: @data

mutable struct AtomicCache{T}
    @atomic value::Union{Nothing, T}
    AtomicCache{T}() where {T} = new{T}(nothing)
end

@data mutable Probe{T} begin
    struct Node
        const cache::AtomicCache{T}
    end
end

x = Probe.Node{Vector{Int}}(AtomicCache{Vector{Int}}())
storage = Moshi.Data.variant_storage(x)
cache = getfield(storage, :cache)
@assert (@atomic :acquire cache.value) === nothing
candidate = [1, 2, 3]
result = @atomicreplace :acquire_release :acquire cache.value nothing => candidate
@assert result.success
@assert (@atomic :acquire cache.value) === candidate
println("atomic cache holder works through Moshi")
