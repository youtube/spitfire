# Introduction #

Design notes for the major Spitfire revisions.

# 0.6.x #

This is a 3-stage design (mostly).
  1. parse the source code (this reports errors, not always in a helpful way, but good enough). lexical and syntactic analysis are combined into one process.
  1. create a new intermediate tree after some 'semantic analysis'. mostly this seems to 'fatten' certain node types with some python pseudo-code. all the nodes are cloned and rebuilt. (not sure why any more)
  1. run over the tree again (twice in later versions) to perform a series of increasingly complex and potentially fragile optimizations. the are performed inline and modify the tree. this sort of works because the optimizer iterates over copies of nodes.

Problems:
  * optimizations are becoming increasingly complex - may require full dependency analysis for new expressions.
  * some optimizations seem to be better suited by a new 'pass' - they don't seem to fit well into the existing model
  * some blurring of where python is injected. 'semantic analyzer' actually does some pseudo-codegen operations.
    * AST actually has some pseudo-codegen too - FunctionNode() generates a function header
    * makes some optimizations more complex - one simple spitfire expression becomes a large chunk of python psuedo-code that is tricky to optimize

# 0.7.x #

Goals:
  * restructure the compiler phases and simplify things
  * enable more complex optimizations
    * filtered placeholder caching
    * hoisting for all types of spitfire primitives - resolve\_udn, resolve\_placeholder

Specifics:
  * remove pseudo-codegen and replace it with a richer abstract syntax
    * use more specific nodes to control code generation