"""Checkpoint sampling and mile ownership allocation."""


def checkpoint_miles(total: float, interval: float) -> list[float]:
    """Generate mile markers along a route at regular intervals.

    First checkpoint is 0.0, last is total. A regular checkpoint closer
    than 0.25 * interval to the destination is dropped.
    """
    if total <= 0:
        return [0.0]

    ms = [0.0]
    m = interval
    while m < total - 0.25 * interval:
        ms.append(m)
        m += interval

    # Destination is always the final checkpoint
    if ms[-1] != total:
        ms.append(total)

    return ms


def owned_lengths(ms: list[float]) -> list[float]:
    """Calculate the miles owned by each checkpoint using Voronoi/midpoints.

    The first checkpoint owns [0, midpoint(0,1)].
    Intermediate checkpoints own [midpoint(i-1, i), midpoint(i, i+1)].
    The final checkpoint owns [midpoint(n-1, n), total].
    Sums exactly to total miles.
    """
    if len(ms) <= 1:
        return [0.0] if not ms else [ms[0]]

    # Midpoint boundaries
    b = [ms[0]] + [(ms[i] + ms[i + 1]) / 2.0 for i in range(len(ms) - 1)] + [ms[-1]]
    return [b[i + 1] - b[i] for i in range(len(ms))]
