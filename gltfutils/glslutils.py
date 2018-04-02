import re
from collections import deque
from itertools import chain
import logging
_logger = logging.getLogger(__name__)


class RE(object):
    DEFINE = re.compile(r'#define\W+(?P<var>\w+)\W*(?P<val>\w*)')
    IFDEF = re.compile(r'#ifdef\W+(?P<var>\w+)')
    IFNDEF = re.compile(r'#ifndef\W+(?P<var>\w+)')
    ELSE = re.compile(r'#else')
    ENDIF = re.compile(r'#endif')
    VERSION = re.compile(r'#version\W+(?P<version>\w+)')
    EXTENSION = re.compile(r'#extension\W+(?P<extension>\w+)')
    ALL = (DEFINE, IFDEF, IFNDEF, ELSE, ENDIF, VERSION, EXTENSION)
    ALL_PP = (DEFINE, IFDEF, IFNDEF, ELSE, ENDIF, VERSION, EXTENSION)


_ATTRIBUTE_DECL_RE = re.compile(r"attribute\s+(?P<type_spec>\w+)\s+(?P<attribute_name>\w+)\s*;")
_UNIFORM_DECL_RE =   re.compile(r"uniform\s+(?P<type_spec>\w+)\s+(?P<uniform_name>\w+)(\[\d*\])?\s*(=\s*(?P<initialization>.*)\s*;|;)")


def preprocess(glsl, defines=None):
    if defines is None:
        defines = {}
    else:
        defines = defines.copy()
    _logger.debug('defines = %s', defines)
    src_lines = glsl.split('\n')
    lines = {i: l for i, l in enumerate(l.partition('//')[0].strip() for l in src_lines)
             if l}
    preprocessed = {}
    pp_matches = {i: m for i, m in ((i, next((m for m in (rex.match(l) for rex in RE.ALL) if m), None))
                                    for i, l in lines.items())
                  if m}
    stack = deque()
    version = '130'
    for i, src_line in enumerate(src_lines):
        if i not in lines:
            continue
        line = lines[i]
        if i in pp_matches:
            _logger.debug('line %d match: %s', i, pp_matches[i])
        if stack and (   (stack[-1].re == RE.IFDEF  and stack[-1][1] not in defines)
                      or (stack[-1].re == RE.IFNDEF and stack[-1][1]     in defines)):
            if i in pp_matches and pp_matches[i].re == RE.ELSE:
                popped = stack.pop()
                _logger.debug('popped %s', popped)
                if not stack:
                    stack.append(pp_matches[i])
                else:
                    stack.append(popped)
                _logger.debug('pushed %s', stack[-1])
            elif i in pp_matches and pp_matches[i].re == RE.ENDIF:
                _logger.debug('popped %s', stack.pop())
            elif i in pp_matches and pp_matches[i].re in (RE.IFDEF, RE.IFNDEF):
                stack.append(stack[-1])
                _logger.debug('pushed %s', stack[-1])
            else:
                continue # skip line in false-testing conditional block
        elif i in pp_matches:
            m = pp_matches[i]
            if m.re == RE.DEFINE and m[1] not in defines:
                defines[m[1]] = m.group(2) if m.group(2) is not None else '1'
            elif m.re in (RE.IFDEF, RE.IFNDEF):
                stack.append(m)
                _logger.debug('pushed %s', m)
            elif m.re == RE.ELSE:
                popped = stack.pop()
                _logger.debug('popped %s', popped)
                if popped.re == RE.IFDEF:
                    stack.append(RE.IFNDEF.match('#ifndef %s' % popped[1]))
                    _logger.debug('pushed %s', stack[-1])
                elif popped.re == RE.IFNDEF:
                    stack.append(RE.IFDEF.match('#ifdef %s' % popped[1]))
                    _logger.debug('pushed %s', stack[-1])
                else:
                    raise Exception('huhh?')
            elif m.re == RE.ENDIF:
                popped = stack.pop()
                _logger.debug('popped %s', popped)
            elif m.re == RE.VERSION:
                version = m[1]
        else:
            preprocessed[i] = line
    return '\n'.join(chain('#version %s' % version,
                           '\n'.join((src_lines[i]
                                      for i in sorted(preprocessed.keys())))))
