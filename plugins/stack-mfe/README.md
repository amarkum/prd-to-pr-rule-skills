# stack-mfe: Module Federation micro-frontend pack

Adds micro-frontend rules on top of `stack-frontend`, which it depends on. Exposed modules are versioned contracts,
shared dependencies are singletons, a failing remote never blanks the host, the shell owns top-level routes, types are
shared through federation DTS, and contract tests cover both sides. The `mfe-remote` skill activates on federation
configs and `src/` files. Install with `/plugin install stack-mfe@ai-sdlc` (this enables `stack-frontend` and `sdlc-core`
too). Owned by the Web Platform Guild.
