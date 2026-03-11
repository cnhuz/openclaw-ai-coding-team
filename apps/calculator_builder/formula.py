from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Callable


class FormulaError(Exception):
    pass


@dataclass
class CompiledFormula:
    source: str
    node: ast.AST


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub, ast.Not)
_ALLOWED_BOOLOPS = (ast.And, ast.Or)
_ALLOWED_CMPOPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def compile_formula(source: str) -> CompiledFormula:
    if not isinstance(source, str) or not source.strip():
        raise FormulaError("formula is empty")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"invalid formula syntax: {e.msg}") from e
    return CompiledFormula(source=source, node=tree.body)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_number(value: Any, what: str) -> float:
    if not _is_number(value):
        raise FormulaError(f"{what} must be a number")
    return float(value)


def _truthy(value: Any) -> bool:
    # Allow bools, numbers, and strings but be deterministic.
    if isinstance(value, bool):
        return value
    if _is_number(value):
        return value != 0
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return bool(value)


def eval_formula(compiled: CompiledFormula, variables: dict[str, Any]) -> Any:
    funcs: dict[str, Callable[..., Any]] = {
        "IF": lambda cond, a, b: a if _truthy(cond) else b,
        "min": lambda *args: min(_require_number(a, "min arg") for a in args),
        "max": lambda *args: max(_require_number(a, "max arg") for a in args),
    }

    def walk(node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, str, bool)) or node.value is None:
                return node.value
            raise FormulaError("unsupported constant")

        if isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            raise FormulaError(f"unknown identifier: {node.id}")

        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, _ALLOWED_BINOPS):
                raise FormulaError("unsupported operator")
            left = walk(node.left)
            right = walk(node.right)
            if isinstance(node.op, ast.Add):
                # support string concat for text fields
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                return _require_number(left, "left") + _require_number(right, "right")
            if isinstance(node.op, ast.Sub):
                return _require_number(left, "left") - _require_number(right, "right")
            if isinstance(node.op, ast.Mult):
                # allow repeat string * int
                if isinstance(left, str) and _is_number(right):
                    return left * int(float(right))
                if isinstance(right, str) and _is_number(left):
                    return right * int(float(left))
                return _require_number(left, "left") * _require_number(right, "right")
            if isinstance(node.op, ast.Div):
                denom = _require_number(right, "right")
                if denom == 0:
                    raise FormulaError("division by zero")
                return _require_number(left, "left") / denom
            if isinstance(node.op, ast.Pow):
                return _require_number(left, "left") ** _require_number(right, "right")
            if isinstance(node.op, ast.Mod):
                denom = _require_number(right, "right")
                if denom == 0:
                    raise FormulaError("modulo by zero")
                return _require_number(left, "left") % denom

        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, _ALLOWED_UNARYOPS):
                raise FormulaError("unsupported unary operator")
            val = walk(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +_require_number(val, "operand")
            if isinstance(node.op, ast.USub):
                return -_require_number(val, "operand")
            if isinstance(node.op, ast.Not):
                return not _truthy(val)

        if isinstance(node, ast.BoolOp):
            if not isinstance(node.op, _ALLOWED_BOOLOPS):
                raise FormulaError("unsupported boolean operator")
            if isinstance(node.op, ast.And):
                for v in node.values:
                    if not _truthy(walk(v)):
                        return False
                return True
            if isinstance(node.op, ast.Or):
                for v in node.values:
                    if _truthy(walk(v)):
                        return True
                return False

        if isinstance(node, ast.Compare):
            if any(not isinstance(op, _ALLOWED_CMPOPS) for op in node.ops):
                raise FormulaError("unsupported comparison operator")
            left = walk(node.left)
            current = left
            for op, comp in zip(node.ops, node.comparators):
                right = walk(comp)
                ok: bool
                if isinstance(op, ast.Eq):
                    ok = current == right
                elif isinstance(op, ast.NotEq):
                    ok = current != right
                elif isinstance(op, ast.Lt):
                    ok = _require_number(current, "left") < _require_number(right, "right")
                elif isinstance(op, ast.LtE):
                    ok = _require_number(current, "left") <= _require_number(right, "right")
                elif isinstance(op, ast.Gt):
                    ok = _require_number(current, "left") > _require_number(right, "right")
                elif isinstance(op, ast.GtE):
                    ok = _require_number(current, "left") >= _require_number(right, "right")
                else:
                    raise FormulaError("unsupported comparison")
                if not ok:
                    return False
                current = right
            return True

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FormulaError("unsupported function reference")
            name = node.func.id
            if name not in funcs:
                raise FormulaError(f"unknown function: {name}")
            args = [walk(arg) for arg in node.args]
            try:
                return funcs[name](*args)
            except TypeError as e:
                raise FormulaError(f"invalid arguments for {name}") from e

        # Disallow everything else: Attribute, Subscript, Lambda, Dict, List, etc.
        raise FormulaError(f"unsupported expression: {node.__class__.__name__}")

    return walk(compiled.node)
