import json
import ast
import sys
from typing import Any, Dict, List, Optional
import click
from symbox.core.engine import SymboxEngine


def print_json_or_text(data: Any, json_output: bool = True) -> None:
    if json_output or isinstance(data, dict):
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        click.echo(str(data))


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
                print_json_or_text({"status": "success", "message": msg, "svo": [s_name, v_name, o_name]})
            else:
                print_json_or_text({"status": "contradiction", "error": msg})
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
    print_json_or_text({"status": "success", "object": subj.to_dict()})


@cli.command("delete")
@click.argument("obj_name")
def delete(obj_name: str) -> None:
    """Delete a Subject and retract its facts."""
    obj_name = obj_name.lstrip("/")
    engine = SymboxEngine()
    success = engine.delete_subject(name=obj_name)
    if success:
        print_json_or_text({"status": "success", "message": f"Object '{obj_name}' deleted."})
    else:
        print_json_or_text({"status": "error", "message": f"Object '{obj_name}' not found."})
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
        print_json_or_text({"status": "success", "message": f"Bound '{func_name}' from '{file_path}' to '{obj_name}'."})
    except Exception as e:
        print_json_or_text({"status": "error", "message": str(e)})
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
        print_json_or_text({"status": "success", "message": f"Unbound '{func_name}' from '{obj_name}'."})
    else:
        print_json_or_text({"status": "error", "message": f"Failed to unbind '{func_name}'."})
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
        # Confirm needed response
        print_json_or_text(conf_data)
        sys.exit(0)
    elif success:
        subj = engine.subjects[obj_name]
        print_json_or_text({"status": "success", "object": subj.to_dict()})
    else:
        print_json_or_text({"status": "error", "message": "Failed to set attributes."})
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
        print_json_or_text({"status": "success", "object": engine.subjects[obj_name].to_dict()})
    else:
        print_json_or_text({"status": "error", "message": f"Object '{obj_name}' not found."})
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
        print_json_or_text({"status": "success", "message": msg, "svo": [s_name, v_name, o_name]})
    else:
        print_json_or_text({"status": "contradiction", "error": msg})
        sys.exit(1)


@cli.command("list")
@click.argument("target", default="objects")
def list_cmd(target: str) -> None:
    """List objects, verbs, worries, backups, or specific entity details."""
    target = target.lstrip("/")
    engine = SymboxEngine()
    data = engine.list_summary(target=target)
    print_json_or_text(data)


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
    print_json_or_text({"status": "success", "backup_id": tag_id, "note": note})


@backup_group.command("rollback")
@click.argument("note_or_id")
def backup_rollback(note_or_id: str) -> None:
    """Rollback state to a snapshot."""
    engine = SymboxEngine()
    try:
        engine.backup.rollback(note_or_id=note_or_id)
        # Reload state after rollback
        engine.load_state()
        print_json_or_text({"status": "success", "message": f"Rolled back to '{note_or_id}'."})
    except Exception as e:
        print_json_or_text({"status": "error", "message": str(e)})
        sys.exit(1)


@backup_group.command("delete")
@click.argument("ids", nargs=-1, required=True)
def backup_delete(ids: List[str]) -> None:
    """Delete specified backup snapshots."""
    engine = SymboxEngine()
    deleted = engine.backup.delete(ids=list(ids))
    print_json_or_text({"status": "success", "deleted": deleted})


@backup_group.command("log")
def backup_log() -> None:
    """View backup snapshot history."""
    engine = SymboxEngine()
    history = engine.backup.log()
    print_json_or_text(history)


def main() -> None:
    # Strip leading slash from sys.argv if invoked as /sbox
    if len(sys.argv) > 1 and sys.argv[1].startswith("/sbox"):
        sys.argv[1] = sys.argv[1].replace("/sbox", "").lstrip()
        if sys.argv[1] == "":
            sys.argv.pop(1)
    cli(obj={})


if __name__ == "__main__":
    main()
