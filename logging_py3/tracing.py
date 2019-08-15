import tracemalloc
import linecache
import os
import logging
import asyncio

LOG = logging.getLogger(__name__)

def display_top(snapshot, compare_to=None, key_type='lineno', limit=10):
    filter_traces = (
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<frozen importlib._bootstrap_external>"),
        tracemalloc.Filter(False, "<unknown>"),
    )

    snapshot = snapshot.filter_traces(filter_traces)

    if compare_to:
        compare_to = compare_to.filter_traces(filter_traces)

        top_stats = snapshot.compare_to(compare_to, key_type)
    else:
        top_stats = snapshot.statistics(key_type)

    LOG.debug("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        LOG.debug("#%s: %s:%s: %.1f KiB"
                  % (index, filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            LOG.debug('    %s' % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        LOG.debug("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    LOG.debug("Total allocated size: %.1f KiB" % (total / 1024))


async def trace_memory_alloc(compare_to, interval=-1, duration=-1):
    LOG.debug('Tracing memory allocation')
    current = tracemalloc.take_snapshot()

    display_top(current, compare_to)

    if interval > 0 and duration > 0:
        await asyncio.sleep(interval)
        asyncio.ensure_future(
            trace_memory_alloc(compare_to, interval, duration - interval))

def start():
    tracemalloc.start()
