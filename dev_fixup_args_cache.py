from pathlib import Path

term = Path("src/terminterface.jl")
s = term.read_text()
helpers = '''@inline function _get_cached_arguments(cache::ArgsCacheT{T}) where {T}\n    return @atomic :acquire cache.value\nend\n\n@inline function _publish_cached_arguments!(cache::ArgsCacheT{T}, candidate::ArgsT{T}) where {T}\n    result = @atomicreplace :acquire_release :acquire cache.value nothing => candidate\n    return result.success ? candidate : result.old::ArgsT{T}\nend\n\n'''
doc = '''\"\"\"\n    arguments(expr)\n'''
if s.count(helpers) != 1 or s.count(doc) != 1:
    raise RuntimeError("unexpected terminterface layout")
s = s.replace(helpers, "", 1)
s = s.replace(doc, helpers + doc, 1)
term.write_text(s)


test = Path("test/threadsafe_arguments.jl")
s = test.read_text()
s = s.replace(
'''function fresh_sum(trial; nargs = 1024)\n    xs = [\n        SymbolicUtils.Sym{SymReal}(Symbol(:threadsafe_args_, trial, :_, i); type = Real)\n        for i in 1:nargs\n    ]\n    return sum(xs)\nend\n''',
'''function fresh_sum(trial; nargs = 1024)\n    xs = [\n        SymbolicUtils.Sym{SymReal}(Symbol(:threadsafe_args_, trial, :_, i); type = Real)\n        for i in 1:nargs\n    ]\n    return sum(xs), xs\nend\n''')
s = s.replace(
'''    expr = fresh_sum(0; nargs = 32)\n    first_args = arguments(expr)\n''',
'''    expr, _ = fresh_sum(0; nargs = 32)\n    first_args = arguments(expr)\n''')
s = s.replace(
'''            expr = fresh_sum(trial)\n            expected = Set(keys(expr.dict))\n''',
'''            expr, xs = fresh_sum(trial)\n            expected = Set(xs)\n''')
s = s.replace(
'''                    collect(arguments(expr))\n''',
'''                    arguments(expr)\n''')
s = s.replace(
'''            results = fetch.(tasks)\n            @test all(length(args) == length(expected) for args in results)\n            @test all(isequal(Set(args), expected) for args in results)\n''',
'''            results = fetch.(tasks)\n            published = parent(first(results))\n            @test all(args -> parent(args) === published, results)\n            @test all(length(args) == length(expected) for args in results)\n            @test all(isequal(Set(args), expected) for args in results)\n''')
test.write_text(s)

print("argument-cache review fixups applied")
