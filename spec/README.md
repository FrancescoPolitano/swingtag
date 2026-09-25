# How this project is specified

placard is built with spec-driven development. Decisions are taken in the spec,
before code, and the code follows the spec. Six phases, in order:

1. **Spikes** (`spec/spikes/`). Small throwaway code that answers one unknown each.
   Stop when the answer is there, not when the code is pretty.
2. **Reference implementation** (`spec/spikes/reference/`). Spikes that answered
   their question are kept and annotated: `PROVES` marks what validates the approach,
   `SHORTCUT` marks what must not be copied.
3. **Spec** (`spec/SPEC.md`). Problem statement, non-goals, assumptions, glossary,
   actors, user stories, functional and technical specification, edge cases. The
   smallest document that specifies without ambiguity; a decision that looks obvious
   is written down anyway.
4. **Test plan** (`spec/TEST-PLAN.md`), written before the implementation plan. Every
   test has a name, an input and an expected output. No vague tests: "rejects
   `javascript:` links" rather than "handles bad links gracefully". This list is the
   definition of done.
5. **Implementation plan** (`plans/`). File by file, function by function, detailed
   enough that the implementer cannot diverge.
6. **Implementation**, driven by the plan.

**Red flag rule.** If the implementation plan or the implementation needs a new
architectural decision, the spec was incomplete: fix the spec first, then the plan.
Never patch a decision into the plan alone.

**Ambiguity rule.** An ambiguity found while writing the spec becomes a new spike or
an explicit question, never a silent choice.

Work is tracked on the GitHub Project linked to this repository: one issue per phase
deliverable, then one issue per implementation task.
