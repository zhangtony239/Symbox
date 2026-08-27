---
name: symbox
description: Use Symbox to externalize and constrain an agent's current symbolic world when multi-step reasoning, cross-object relationships, changing assumptions, or persistent worries could cause contradictions. Apply it to model objects and checks, synchronize current beliefs with `sbox now`, inspect structured results, and revise the model when validation or truth maintenance reports a problem; do not use it as a project manager or an external fact verifier.
---

# Use Symbox as a cognitive guardrail

Use Symbox to keep an external, inspectable model of what you currently believe or are considering. Encode important constraints in that model, synchronize each material change in your reasoning, and treat reported conflicts as evidence that your assumptions or model need attention.

Do not use Symbox to manage tasks, dependencies, source files, or project scaffolding. Do not treat it as an authority about facts that you have not supplied.

## Build the right mental model

- **Object**: an entity, concept, state, or metacognitive concern in your current symbolic world. Objects may be physical, abstract, or meta-level.
- **Adj**: an attribute of an object and a place to attach a check that constrains an object's acceptable state.
- **Verb**: a relationship whose bound check validates its subject and any additional arguments.
- **Worry**: a persistent metacognitive condition to monitor as the modeled world changes.
- **`now`**: an atomic assertion of what you think now, represented as Subject + Verb + a variable-length argument package.

Use one polarity for every bound check, including Worry conditions:

- Return `True` when the candidate state is normal and the check passes.
- Return `False` when the candidate should trigger a conflict.

Symbox detects conflicts only within the facts, relationships, checks, and truth-propagation paths represented in the current model. A result with no conflict means only that no conflict was found within those boundaries. It does not prove external reality, establish arbitrary logical completeness, or eliminate hallucinations.

## Follow the cognitive loop

### 1. Choose a project-local world

Run commands from the project whose symbolic state you intend to maintain, or pass the global `--root PATH` option before the subcommand. Do not mix unrelated reasoning contexts into one root.

Inspect the installed command contract when needed:

```bash
sbox --version
sbox --help
sbox bind --help
sbox now --help
```

Read every command's JSON result rather than inferring success from prose or intent.

### 2. Externalize relevant objects

Create only the entities and concerns needed for the current reasoning chain:

```bash
sbox create robot
sbox create moves --category abstract
sbox create deployment_risk --category meta
sbox set robot 'mode="ready"' battery=80
```

Treat attributes as current modeled cognition, not independently verified facts. Query committed state when you need to reorient:

```bash
sbox list objects
sbox list robot
```

### 3. Encode checks instead of remembering constraints only in prose

Put executable relationship constraints in a Verb check. Put object-state constraints in an Adj or other non-Verb binding. Model a persistent concern as a Worry condition, preserving the same `True`-is-normal and `False`-is-conflict polarity.

For example, create a project-local check:

```python
def moves(subject, destination, speed=1):
    return subject == "robot" and bool(destination) and speed > 0
```

Then bind the relationship object as a Verb:

```bash
sbox bind moves -f rules/checks.py --verb
```

If the function inside that file is named `validate_move` instead of matching the object name, provide that callable name after the object name:

```bash
sbox bind moves validate_move -f rules/checks.py --verb
```

Use `sbox bind --help` before constructing a binding that depends on loader-specific naming. Do not leave a critical rule only in the conversation and assume Symbox can enforce it.

### 4. Synchronize what you think now

Use this current CLI shape:

```text
sbox now SUBJECT VERB [ARGUMENT ...]
```

The trailing package may contain zero, one, or many positional and named arguments. Choose names that match the bound Python function; do not impose a fixed semantic-role vocabulary.

```bash
# Zero trailing arguments: the subject itself changes state.
sbox now door opens

# One positional argument.
sbox now robot moves dock

# Multiple positional and named arguments.
sbox now robot moves dock speed=2
```

The subject remains the explicit first argument to the Verb check. Additional tokens are parsed as its variable-length argument package. Missing required parameters, invalid values, failed checks, and propagated conflicts abort the atomic assertion; a failed candidate does not enter the symbolic world.

Synchronize again after every material change in assumptions, relationships, attributes, or concerns. Query the affected objects or relation result before relying on the updated model.

### 5. Handle the structured result

Parse the JSON envelope and branch on `status`:

- **`success`**: use `data` as the committed result. For `now`, retain the returned `subject`, `verb`, and `node_key` when they matter to subsequent reasoning.
- **`confirm_needed`**: stop and inspect the proposed and existing values in `data`. Ask for or obtain explicit confirmation through the capabilities actually exposed by the installed CLI. Do not assume confirmation, silently choose a value, or invent a successful write. Check `sbox <command> --help` before retrying because confirmation options are version-specific.
- **`error`**: inspect every entry in `diagnostics`, correct malformed names, missing arguments, unavailable bindings, or other validation problems, and retry only after correcting the input or model.
- **`conflict`**: inspect `diagnostics`, `conflicts`, and `transaction_id`. Revisit the assumptions, encoded checks, and supporting evidence that produced the candidate. Correct or retract the faulty cognition before trying again.

Treat both the JSON `status` and the process exit code as signals. Confirmation may use a successful exit code; validation errors and conflicts may use non-zero exit codes. Never replace the returned envelope with a fabricated success result.

## Apply these safeguards

- Do not bypass or weaken a check merely to make an assertion commit.
- Do not write a contradictory state with another mechanism and claim Symbox accepted it.
- Do not equate absence of a reported conflict with proof that the modeled claim is true in the outside world.
- Do not encode unknown information as known merely to complete the model.
- When information is missing, preserve the uncertainty, gather evidence, or revise the model before retrying.
- When your cognition changes, update Symbox rather than continuing from stale symbolic state.

Use `sbox --help` and subcommand help as the source of truth for exact installed CLI syntax. Consult the repository's `symbox-design-spec-v0.6.md` for the deeper SVK and truth-maintenance design boundaries.
