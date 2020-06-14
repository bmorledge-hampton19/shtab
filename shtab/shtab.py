from __future__ import print_function
from functools import total_ordering
import io
import logging

__all__ = ["Optional", "Required", "complete"]
logger = logging.getLogger(__name__)
GLOBAL_OPTIONS = ["-h", "--help", "-q", "--quiet", "-v", "--verbose"]
ROOT_PREFIX = "_dvc"
UNCOMPLETABLE_POSITIONALS = {
    "rev",
    "url",
    "args",
    "name",
    "option",
    "value",
    "command",
}


def print_bash_commands(parser, prefix=ROOT_PREFIX, fd=None):
    """Recursive parser traversal, printing bash helper syntax."""
    positionals = parser._get_positional_actions()
    commands = []

    if prefix == ROOT_PREFIX:  # skip root options
        pass
    else:
        opts = [
            opt for sub in positionals if sub.choices for opt in sub.choices
        ]
        opts += sum(
            (opt.option_strings for opt in parser._get_optional_actions()), []
        )
        # use list rather than set to maintain order
        opts = [i for i in opts if i not in GLOBAL_OPTIONS]
        opts = " ".join(opts)
        print(f"{prefix}='{opts}'", file=fd)

    dest = []
    for sub in positionals:
        if sub.choices:
            for cmd in sorted(sub.choices):
                commands.append(cmd)
                print_bash_commands(
                    sub.choices[cmd], f"{prefix}_{cmd.replace('-', '_')}", fd
                )
        elif not any(i in sub.dest for i in UNCOMPLETABLE_POSITIONALS):
            dest.append(sub.dest)
        else:
            logger.debug(f"uncompletable:{prefix}:{dest}")
    if dest:
        if not {"targets", "target"}.intersection(dest):
            print(f"{prefix}_COMPGEN=_dvc_compgen_files", file=fd)
            logger.debug(f"file:{prefix}:{dest}")
        else:
            print(f"{prefix}_COMPGEN=_dvc_compgen_DVCFiles", file=fd)
            logger.debug(f"DVCFile:{prefix}:{dest}")

    if commands:
        logger.debug(f"subcommands:{prefix}:{commands}")
    return commands


def print_bash(parser, fd=None):
    """Prints definitions in bash syntax for use in autocompletion scripts."""
    bash = io.StringIO()
    commands = print_bash_commands(parser, fd=bash)

    print(
        """\
#!/usr/bin/env bash
# AUTOMATCALLY GENERATED from `dvc completion`
# References:
#   - https://www.gnu.org/software/bash/manual/html_node/\
Programmable-Completion.html
#   - https://opensource.com/article/18/3/creating-bash-completion-script
#   - https://stackoverflow.com/questions/12933362

_dvc_commands='"""
        + " ".join(commands)
        + """'

_dvc_options='-h --help -V --version'
_dvc_global_options='"""
        + " ".join(GLOBAL_OPTIONS)
        + """'

"""
        + bash.getvalue()
        + """
# $1=COMP_WORDS[1]
_dvc_compgen_DVCFiles() {
  compgen -f -X '!*?.dvc' -- $1
  compgen -d -S '/' -- $1  # recurse into subdirs
  # Note that the recurse into dirs is only for looking for DVC-files.
  # Since dirs themselves are not required, we need `-o nospace` at the bottom
  # unfortunately :(
}

# $1=COMP_WORDS[1]
_dvc_compgen_files() {
  compgen -f -- $1
  compgen -d -S '/' -- $1  # recurse into subdirs
}

# $1=COMP_WORDS[1]
_dvc_replace_hyphen() {
  echo $1 | sed 's/-/_/g'
}

# $1=COMP_WORDS[1]
_dvc_compgen_command() {
  local flags_list="_dvc_$(_dvc_replace_hyphen $1)"
  local args_gen="${flags_list}_COMPGEN"
  COMPREPLY=( $(compgen -W "$_dvc_global_options ${!flags_list}" -- "$word"; \
[ -n "${!args_gen}" ] && ${!args_gen} "$word") )
}

# $1=COMP_WORDS[1]
# $2=COMP_WORDS[2]
_dvc_compgen_subcommand() {
  local flags_list="_dvc_$(_dvc_replace_hyphen $1)_$(_dvc_replace_hyphen $2)"
  local args_gen="${flags_list}_COMPGEN"
  [ -n "${!args_gen}" ] && local opts_more="$(${!args_gen} "$word")"
  local opts="${!flags_list}"
  if [ -z "$opts$opts_more" ]; then
    _dvc_compgen_command $1
  else
    COMPREPLY=( $(compgen -W "$_dvc_global_options $opts" -- "$word"; \
[ -n "$opts_more" ] && echo "$opts_more") )
  fi
}

# Notes:
# `COMPREPLY` contains what will be rendered after completion is triggered
# `word` refers to the current typed word
# `${!var}` is to evaluate the content of `var`
# and expand its content as a variable
#       hello="world"
#       x="hello"
#       ${!x} ->  ${hello} ->  "world"
_dvc() {
  local word="${COMP_WORDS[COMP_CWORD]}"

  COMPREPLY=()

  if [ "${COMP_CWORD}" -eq 1 ]; then
    case "$word" in
      -*) COMPREPLY=($(compgen -W "$_dvc_options" -- "$word")) ;;
      *) COMPREPLY=($(compgen -W "$_dvc_commands" -- "$word")) ;;
    esac
  elif [ "${COMP_CWORD}" -eq 2 ]; then
    _dvc_compgen_command ${COMP_WORDS[1]}
  elif [ "${COMP_CWORD}" -ge 3 ]; then
    _dvc_compgen_subcommand ${COMP_WORDS[1]} ${COMP_WORDS[2]}
  fi

  return 0
}

complete -o nospace -F _dvc dvc""",
        file=fd,
    )

@total_ordering
class Choice(object):
    """
    Placeholder, usage:
    >>> ArgumentParser.add_argument(..., choices=[Choice("<type>")])
    to mark a special completion `<type>`.
    """
    def __init__(self, choice_type, required=False):
        self.required = required
        self.type = choice_type

    def __cmp__(self, other):
        if self.required:
            return 0 if other else -1
        return 0

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0


class Optional(object):
    """Example: `ArgumentParser.add_argument(..., choices=Optional.FILE)`"""
    FILE = [Choice("file")]
    DIR = DIRECTORY = [Choice("directory")]


class Required(object):
    """Example: `ArgumentParser.add_argument(..., choices=Required.FILE)`"""
    FILE = [Choice("file", True)]
    DIR = DIRECTORY = [Choice("directory", True)]


def complete(parser, shell="bash", **kwargs):
    logger.debug(str((shell, kwargs, parser)))

    output = io.StringIO()
    if shell == "bash":
        print_bash(parser, output)
    else:
        raise NotImplementedError
    return output.getvalue()
