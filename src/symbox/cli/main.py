"""The ``sbox`` command entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from symbox import __version__
from symbox.application.errors import ErrorCategory
from symbox.cli.results import Diagnostic, ResultEnvelope, ResultStatus
from symbox.cli.runtime import CommandRuntime
from symbox.domain.models import DomainInvariantError, ObjectCategory
from symbox.integrations.python_bindings import BindingLoadError
from symbox.persistence.backup_repository import BackupError, BackupNotFoundError
from symbox.persistence.state_format import StateFormatError


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(prog="sbox", description="Symbox v0.6 CLI")
    parser.add_argument("--version", action="store_true", help="return version information")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root")
    commands = parser.add_subparsers(dest="command")

    create = commands.add_parser("create", help="create a named object")
    create.add_argument("name")
    create.add_argument(
        "--category",
        choices=tuple(category.value for category in ObjectCategory),
        default=ObjectCategory.PHYSICAL.value,
    )
    delete = commands.add_parser("delete", help="delete a named object")
    delete.add_argument("name")

    bind = commands.add_parser("bind", help="bind project-local Python code")
    bind.add_argument("name")
    bind.add_argument("qualified_name", nargs="?")
    bind.add_argument("-f", "--file", required=True)
    bind.add_argument("--verb", action="store_true")
    unbind = commands.add_parser("unbind", help="remove an object's binding")
    unbind.add_argument("name")

    set_command = commands.add_parser("set", help="atomically set attributes")
    set_command.add_argument("name")
    set_command.add_argument("assignments", nargs="+")
    unset = commands.add_parser("unset", help="atomically unset attributes")
    unset.add_argument("name")
    unset.add_argument("keys", nargs="+")

    now = commands.add_parser("now", help="assert a variable-arity SVK relation")
    now.add_argument("subject")
    now.add_argument("verb")
    now.add_argument("arguments", nargs="*")

    list_command = commands.add_parser("list", help="query committed state")
    list_command.add_argument("target")

    backup = commands.add_parser("backup", help="manage project-local backups")
    backup_commands = backup.add_subparsers(dest="backup_command", required=True)
    backup_create = backup_commands.add_parser("create", help="create a backup")
    backup_create.add_argument("note")
    backup_commands.add_parser("list", help="list backups")
    backup_delete = backup_commands.add_parser("delete", help="delete backups")
    backup_delete.add_argument("commit_ids", nargs="+")
    backup_rollback = backup_commands.add_parser("rollback", help="restore a backup")
    backup_rollback.add_argument("commit_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line adapter."""
    arguments = build_parser().parse_args(argv)
    try:
        runtime = CommandRuntime(arguments.root)
        if arguments.version:
            data: object = {"version": __version__}
        elif arguments.command == "create":
            data = runtime.create(arguments.name, arguments.category)
        elif arguments.command == "delete":
            data = runtime.delete(arguments.name)
        elif arguments.command == "bind":
            data = runtime.bind(
                arguments.name,
                arguments.file,
                arguments.qualified_name or arguments.name,
                is_verb=arguments.verb,
            )
        elif arguments.command == "unbind":
            data = runtime.unbind(arguments.name)
        elif arguments.command == "set":
            data = runtime.set_attributes(arguments.name, tuple(arguments.assignments))
        elif arguments.command == "unset":
            data = runtime.unset_attributes(arguments.name, tuple(arguments.keys))
        elif arguments.command == "now":
            data = runtime.now((arguments.subject, arguments.verb, *arguments.arguments))
        elif arguments.command == "list":
            data = runtime.list(arguments.target)
        elif arguments.command == "backup" and arguments.backup_command == "create":
            data = runtime.backup_create(arguments.note)
        elif arguments.command == "backup" and arguments.backup_command == "list":
            data = runtime.backup_list()
        elif arguments.command == "backup" and arguments.backup_command == "delete":
            data = runtime.backup_delete(tuple(arguments.commit_ids))
        elif arguments.command == "backup" and arguments.backup_command == "rollback":
            data = runtime.backup_rollback(arguments.commit_id)
        else:
            data = {"command": "sbox"}
        result = ResultEnvelope(status=ResultStatus.SUCCESS, data=data)
    except BackupNotFoundError as error:
        result = _error_result(error, ErrorCategory.NOT_FOUND, "backup_not_found")
    except BindingLoadError as error:
        result = _error_result(error, ErrorCategory.BINDING, "binding_error")
    except DomainInvariantError as error:
        result = _error_result(error, ErrorCategory.VALIDATION, "validation_error")
    except (BackupError, StateFormatError) as error:
        result = _error_result(error, ErrorCategory.PERSISTENCE, "persistence_error")
    print(result.to_json())
    return int(result.exit_code)


def _error_result(error: Exception, category: ErrorCategory, code: str) -> ResultEnvelope:
    return ResultEnvelope(
        status=ResultStatus.ERROR,
        diagnostics=(Diagnostic(category, code, str(error)),),
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
