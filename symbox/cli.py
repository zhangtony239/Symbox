import ast
import json
import sys
from typing import Any, Dict, List
import click
from symbox.core.engine import SymboxEngine


def echo_error(message: str) -> None:
    """Print an error message to stderr (callers are responsible for exit code)."""
    click.echo(f"error: {message}", err=True)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "-"
    if isinstance(value, (list, set)):
        return ", ".join(str(v) for v in value) if value else "-"
    if isinstance(value, dict):
        return ", ".join(f"{k}={_format_value(v)}" for k, v in value.items()) if value else "-"
    return str(value)


def format_subject(data: Dict[str, Any]) -> str:
    """Format a Subject/Worry dict as human-readable text."""
    lines = [f"{data.get('name', '?')} ({data.get('kind', 'physical')})"]

    watch = data.get("watch_subject_name")
    if watch:
        lines.append(f"  watches: {watch}")
        lines.append(f"  active: {_format_value(data.get('is_active'))}")
        if data.get("func_name"):
            lines.append(f"  condition: {data['func_name']} ({data.get('module_path', '-')})")

    attributes = data.get("attributes") or {}
    if attributes:
        lines.append("  attributes:")
        for k, v in attributes.items():
            lines.append(f"    {k}: {_format_value(v)}")

    adj = data.get("adj") or {}
    if adj:
        lines.append("  adj:")
        for k, v in adj.items():
            value = v.get("value") if isinstance(v, dict) else v
            lines.append(f"    {k} = {_format_value(value)}")

    tags = data.get("tags") or []
    if tags:
        lines.append(f"  tags: {', '.join(tags)}")

    return "\n".join(lines)


def format_verb(data: Dict[str, Any]) -> str:
    """Format a Verb dict as human-readable text."""
    lines = [f"{data.get('name', '?')} (verb)"]
    if data.get("func_name"):
        lines.append(f"  check: {data['func_name']} ({data.get('module_path', '-')})")
    if data.get("domain"):
        lines.append(f"  domain: {_format_value(data['domain'])}")
    if data.get("range"):
        lines.append(f"  range: {_format_value(data['range'])}")
    if data.get("veto_rules"):
        lines.append(f"  veto: {_format_value(data['veto_rules'])}")
    if data.get("modify_rules"):
        lines.append(f"  modify: {_format_value(data['modify_rules'])}")
    return "\n".join(lines)


def format_backup(entry: Dict[str, Any]) -> str:
    """Format one backup log entry as a single line."""
    return f"{entry.get('commit', '????????')}  {entry.get('timestamp', '-')}  {entry.get('note', '-')}"


def print_listing(data: Any) -> None:
    """Print list_summary() output (subjects, verbs, backups, or single entity)."""
    if isinstance(data, dict):
        if "error" in data:
            echo_error(data["error"])
            sys.exit(1)
        # Single entity: subject or verb
        if data.get("is_verb") or "veto_rules" in data:
            click.echo(format_verb(data))
        else:
            click.echo(format_subject(data))
        return

    if not data:
        click.echo("(empty)")
        return

    blocks = []
    for item in data:
        if "commit" in item and "note" in item:
            blocks.append(format_backup(item))
        elif item.get("is_verb") or "veto_rules" in item:
            blocks.append(format_verb(item))
        else:
            blocks.append(format_subject(item))
    click.echo("\n\n".join(blocks))


def parse_kv_input(raw_input: str) -> Dict[str, Any]:
    """Parse dictionary or key:value strings into Python dict."""
    raw = raw_input.strip()
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        # Replace true/false/null with True/False/None for ast.literal_eval fallback
        fixed_raw = raw.replace("true", "True").replace("false", "False").replace("null", "None")
        try:
            return json.loads(raw)
        except Exception:
            try:
                return ast.literal_eval(fixed_raw)
            except Exception:
                pass

    # Try k:v or k=v
    result = {}
    items = raw.split(",") if "," in raw else raw.split()
    for item in items:
        if ":" in item:
            k, v = item.split(":", 1)
        elif "=" in item:
            k, v = item.split("=", 1)
        else:
            k, v = item, "True"
        k = k.strip().strip("'\"")
        v = v.strip().strip("'\"")
        if v.lower() == "true":
            parsed_v = True
        elif v.lower() == "false":
            parsed_v = False
        else:
            try:
                parsed_v = float(v) if "." in v else int(v)
            except ValueError:
                parsed_v = v
        result[k] = parsed_v
    return result


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Symbox: Syntax-driven symbolic reasoning sandbox CLI."""
    if ctx.invoked_subcommand is None:
        # Handle fallback for raw SVO assertion: sbox S V O [--if-force]
        args = ctx.args
        if not args:
            click.echo(ctx.get_help())
            return

        # Strip optional leading /sbox or / from arguments
        clean_args = [a[1:] if a.startswith("/") else a for a in args]

        # Check if first arg is /sbox or sbox
        if clean_args[0] in ("sbox", "sbox"):
            clean_args = clean_args[1:]

        if len(clean_args) >= 3:
            s_name, v_name, o_name = clean_args[0], clean_args[1], clean_args[2]
            if_force = "--if-force" in clean_args
            engine = SymboxEngine()
            success, msg = engine.assert_svo(s_name, v_name, o_name, if_force=if_force)
            if success:
                click.echo(f"asserted: {s_name} {v_name} {o_name}")
            else:
                echo_error(f"contradiction: {msg}")
                sys.exit(1)
        else:
            click.echo(ctx.get_help())


@cli.command("create")
@click.argument("obj_name")
@click.option("--kind", default="physical", help="Object kind: physical, abstract, or meta.")
def create(obj_name: str, kind: str) -> None:
    """Create a Subject or meta object."""
    obj_name = obj_name.lstrip("/")
    engine = SymboxEngine()
    subj = engine.create_subject(name=obj_name, kind=kind)
    click.echo(f"created: {subj.name} ({subj.kind})")


@cli.command("delete")
@click.argument("obj_name")
def delete(obj_name: str) -> None:
    """Delete a Subject and retract its facts."""
    obj_name = obj_name.lstrip("/")
    engine = SymboxEngine()
    success = engine.delete_subject(name=obj_name)
    if success:
        click.echo(f"deleted: {obj_name}")
    else:
        echo_error(f"object '{obj_name}' not found")
        sys.exit(1)


@cli.command("bind")
@click.argument("obj_name")
@click.argument("func_name")
@click.option("-f", "--file", "file_path", required=True, help="Path to Python file.")
@click.option("--verb", is_flag=True, help="Mark target as verb.")
def bind(obj_name: str, func_name: str, file_path: str, verb: bool) -> None:
    """Bind a Python logic function or Worry condition to an object or verb."""
    obj_name = obj_name.lstrip("/")
    engine = SymboxEngine()
    try:
        engine.bind_function(target_name=obj_name, func_name=func_name, file_path=file_path, is_verb=verb)
        target_kind = "verb" if verb else "object"
        click.echo(f"bound: {func_name} ({file_path}) -> {target_kind} '{obj_name}'")
    except Exception as e:
        echo_error(str(e))
        sys.exit(1)


@cli.command("unbind")
@click.argument("obj_name")
@click.argument("func_name")
@click.option("--verb", is_flag=True, help="Target is a verb.")
def unbind(obj_name: str, func_name: str, verb: bool) -> None:
    """Unbind a logic function or Worry condition."""
    obj_name = obj_name.lstrip("/")
    engine = SymboxEngine()
    success = engine.unbind_function(target_name=obj_name, func_name=func_name, is_verb=verb)
    if success:
        click.echo(f"unbound: {func_name} from '{obj_name}'")
    else:
        echo_error(f"failed to unbind '{func_name}' from '{obj_name}'")
        sys.exit(1)


@cli.command("set")
@click.argument("obj_name")
@click.argument("kv_data")
@click.option("--force", is_flag=True, help="Force update, bypassing embedding similarity confirmation.")
def set_cmd(obj_name: str, kv_data: str, force: bool) -> None:
    """Set attributes or Adj patches on an object with threshold detection."""
    obj_name = obj_name.lstrip("/")
    kv_pairs = parse_kv_input(kv_data)
    engine = SymboxEngine()

    success, conf_data = engine.set_attributes(obj_name=obj_name, kv_pairs=kv_pairs, force=force)
    if not success and conf_data:
        # Confirm needed: JSON response (spec v0.4 §2.5), exit 0 so the agent can retry with --force
        click.echo(json.dumps(conf_data, ensure_ascii=False))
        sys.exit(0)
    elif success:
        subj = engine.subjects[obj_name]
        click.echo(f"updated: {obj_name}")
        click.echo(format_subject(subj.to_dict()))
    else:
        echo_error(f"failed to set attributes on '{obj_name}'")
        sys.exit(1)


@cli.command("unset")
@click.argument("obj_name")
@click.argument("keys", nargs=-1, required=True)
def unset(obj_name: str, keys: List[str]) -> None:
    """Unset attributes or Adj patches on an object."""
    obj_name = obj_name.lstrip("/")
    engine = SymboxEngine()
    success = engine.unset_attributes(obj_name=obj_name, keys=list(keys))
    if success:
        click.echo(f"unset: {', '.join(keys)} on '{obj_name}'")
    else:
        echo_error(f"object '{obj_name}' not found")
        sys.exit(1)


@cli.command("svo")
@click.argument("s_name")
@click.argument("v_name")
@click.argument("o_name")
@click.option("--if-force", is_flag=True, help="Force assertion by adjusting conflicting assumptions.")
def svo_cmd(s_name: str, v_name: str, o_name: str, if_force: bool) -> None:
    """Assert an S V O ground relation."""
    s_name = s_name.lstrip("/")
    v_name = v_name.lstrip("/")
    o_name = o_name.lstrip("/")
    engine = SymboxEngine()

    success, msg = engine.assert_svo(s_name, v_name, o_name, if_force=if_force)
    if success:
        click.echo(f"asserted: {s_name} {v_name} {o_name}")
    else:
        echo_error(f"contradiction: {msg}")
        sys.exit(1)


@cli.command("list")
@click.argument("target", default="objects")
def list_cmd(target: str) -> None:
    """List objects, verbs, worries, backups, or specific entity details."""
    target = target.lstrip("/")
    engine = SymboxEngine()
    data = engine.list_summary(target=target)
    print_listing(data)


@cli.group("backup")
def backup_group() -> None:
    """Snapper-style backup version control subcommands."""
    pass


@backup_group.command("create")
@click.argument("note")
def backup_create(note: str) -> None:
    """Create a new backup snapshot."""
    engine = SymboxEngine()
    tag_id = engine.backup.create(note=note)
    click.echo(f"backup created: {tag_id}")


@backup_group.command("rollback")
@click.argument("note_or_id")
def backup_rollback(note_or_id: str) -> None:
    """Rollback state to a snapshot."""
    engine = SymboxEngine()
    try:
        engine.backup.rollback(note_or_id=note_or_id)
        # Reload state after rollback
        engine.load_state()
        click.echo(f"rolled back to: {note_or_id}")
    except Exception as e:
        echo_error(str(e))
        sys.exit(1)


@backup_group.command("delete")
@click.argument("ids", nargs=-1, required=True)
def backup_delete(ids: List[str]) -> None:
    """Delete specified backup snapshots."""
    engine = SymboxEngine()
    deleted = engine.backup.delete(ids=list(ids))
    if deleted:
        click.echo(f"backup deleted: {', '.join(deleted)}")
    else:
        click.echo("no backups deleted.")


@backup_group.command("log")
def backup_log() -> None:
    """View backup snapshot history."""
    engine = SymboxEngine()
    history = engine.backup.log()
    if not history:
        click.echo("(no backups)")
        return
    for entry in history:
        click.echo(format_backup(entry))


def main() -> None:
    # Strip leading slash from sys.argv if invoked as /sbox
    if len(sys.argv) > 1 and sys.argv[1].startswith("/sbox"):
        sys.argv[1] = sys.argv[1].replace("/sbox", "").lstrip()
        if sys.argv[1] == "":
            sys.argv.pop(1)
    cli(obj={})


if __name__ == "__main__":
    main()
