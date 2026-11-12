"""Read and verify saved optimization results without running a solver."""

import json
import math
from pathlib import Path
from typing import Annotated, Literal

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, ValidationError

from freight_intelligence.optimization.transport import INTERPRETATION

Nonnegative = Annotated[FiniteFloat, Field(ge=0)]
Name = Annotated[str, Field(min_length=1)]


class Summary(BaseModel):
    model_config = ConfigDict(strict=True)
    scenario: Name
    status: Literal["optimal"]
    solver: Literal["scipy-highs"]
    total_cost: Nonnegative
    total_supply: Nonnegative
    flow_unit: Name
    cost_unit: Name
    max_balance_residual: Annotated[FiniteFloat, Field(ge=0, le=1e-7)]
    interpretation: str
    input_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Arc(BaseModel):
    model_config = ConfigDict(strict=True)
    arc_id: Name
    origin: Name
    destination: Name
    flow: Nonnegative
    capacity: Nonnegative
    unit_cost: Nonnegative
    total_cost: Nonnegative
    utilization: Annotated[FiniteFloat, Field(ge=0, le=1.0000001)] | None


class Node(BaseModel):
    model_config = ConfigDict(strict=True)
    node_id: Name
    balance: FiniteFloat
    net_outflow: FiniteFloat
    residual: Annotated[FiniteFloat, Field(ge=-1e-7, le=1e-7)]


def load_transport_results(directory: Path):
    """Validate the full saved bundle before returning a filtered public view."""
    try:
        summary = Summary.model_validate_json((directory / "summary.json").read_text())
        if summary.interpretation != INTERPRETATION:
            raise ValueError("Unexpected interpretation")
        arcs = [
            Arc.model_validate(row)
            for row in pl.read_parquet(directory / "allocation.parquet").to_dicts()
        ]
        nodes = [
            Node.model_validate(row)
            for row in pl.read_parquet(directory / "node_balances.parquet").to_dicts()
        ]
        if not arcs or not nodes or len({arc.arc_id for arc in arcs}) != len(arcs):
            raise ValueError("Empty results or duplicate arc identifiers")
        if len({node.node_id for node in nodes}) != len(nodes):
            raise ValueError("Duplicate node identifiers")
        incoming = {node.node_id: [] for node in nodes}
        outgoing = {node.node_id: [] for node in nodes}
        for arc in arcs:
            if (
                arc.origin not in outgoing
                or arc.destination not in incoming
                or arc.origin == arc.destination
            ):
                raise ValueError("Invalid endpoints")
            if arc.flow > arc.capacity + 1e-7:
                raise ValueError("Capacity exceeded")
            if not math.isclose(
                arc.total_cost, arc.flow * arc.unit_cost, rel_tol=1e-7, abs_tol=1e-7
            ):
                raise ValueError("Inconsistent arc cost")
            expected = arc.flow / arc.capacity if arc.capacity else None
            if (expected is None) != (arc.utilization is None):
                raise ValueError("Invalid utilization")
            if expected is not None and not math.isclose(expected, arc.utilization, abs_tol=1e-7):
                raise ValueError("Inconsistent utilization")
            outgoing[arc.origin].append(arc.flow)
            incoming[arc.destination].append(arc.flow)
        for node in nodes:
            net = math.fsum(outgoing[node.node_id]) - math.fsum(incoming[node.node_id])
            if not math.isclose(net, node.balance, rel_tol=0.0, abs_tol=1e-7):
                raise ValueError("Flow conservation failed")
            if not math.isclose(net, node.net_outflow, rel_tol=0.0, abs_tol=1e-7):
                raise ValueError("Inconsistent node outflow")
            if not math.isclose(node.residual, net - node.balance, rel_tol=0.0, abs_tol=1e-7):
                raise ValueError("Inconsistent node residual")
        if not math.isclose(
            summary.total_cost,
            math.fsum(arc.total_cost for arc in arcs),
            rel_tol=1e-7,
            abs_tol=1e-7,
        ):
            raise ValueError("Inconsistent objective")
        supply = math.fsum(max(node.balance, 0.0) for node in nodes)
        if not math.isclose(summary.total_supply, supply, rel_tol=1e-7, abs_tol=1e-7):
            raise ValueError("Inconsistent total supply")
        return (
            summary.model_dump(),
            [arc.model_dump() for arc in arcs],
            [node.model_dump() for node in nodes],
        )
    except (
        OSError,
        ValueError,
        OverflowError,
        json.JSONDecodeError,
        ValidationError,
        pl.exceptions.PolarsError,
    ) as error:
        # Do not expose filesystem locations or raw solver metadata to callers.
        raise ValueError("Saved transport results are missing or inconsistent") from error
