# Solving

Solving a dependency consists of 2 steps:

1. Locate all sub dependencies from binds or autowiring.
1. Topologically sort sub dependencies and group them such that subdependencies that do not depend on eachother can be executed in parallel.
