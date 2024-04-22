package jcarbon.cpu.jiffies;

import static java.util.stream.Collectors.joining;

import java.time.Instant;
import java.util.Arrays;
import jcarbon.cpu.SystemComponent;
import jcarbon.data.Component;
import jcarbon.data.Interval;

/** An {@link Interval} of cpu jiffies over a time range. */
public final class SystemJiffies implements Interval<CpuJiffies[]>, Comparable<SystemJiffies> {
  public static SystemJiffies between(SystemSample first, SystemSample second) {
    if (first.compareTo(second) > -1) {
      throw new IllegalArgumentException(
          String.format(
              "first sample is not before second sample (%s !< %s)",
              first.timestamp(), second.timestamp()));
    }
    return new SystemJiffies(
        first.timestamp(), second.timestamp(), difference(first.data(), second.data()));
  }

  private static CpuJiffies[] difference(CpuJiffies[] first, CpuJiffies[] second) {
    if (first.length != second.length) {
      throw new IllegalArgumentException(
          String.format(
              "readings do not have the same number of cpus (%s != %s)",
              first.length, second.length));
    }
    CpuJiffies[] jiffies = new CpuJiffies[first.length];
    for (CpuJiffies cpu : first) {
      jiffies[cpu.component.cpu] =
          new CpuJiffies(
              cpu.component,
              second[cpu.component.cpu].user - cpu.user,
              second[cpu.component.cpu].nice - cpu.nice,
              second[cpu.component.cpu].system - cpu.system,
              second[cpu.component.cpu].idle - cpu.idle,
              second[cpu.component.cpu].iowait - cpu.iowait,
              second[cpu.component.cpu].irq - cpu.irq,
              second[cpu.component.cpu].softirq - cpu.softirq,
              second[cpu.component.cpu].steal - cpu.steal,
              second[cpu.component.cpu].guest - cpu.guest,
              second[cpu.component.cpu].guestNice - cpu.guestNice);
    }
    return jiffies;
  }

  private final Instant start;
  private final Instant end;
  private final CpuJiffies[] jiffies;

  SystemJiffies(Instant start, Instant end, CpuJiffies[] jiffies) {
    this.start = start;
    this.end = end;
    this.jiffies = Arrays.copyOf(jiffies, jiffies.length);
  }

  @Override
  public Instant start() {
    return start;
  }

  @Override
  public Instant end() {
    return end;
  }

  @Override
  public Component component() {
    return SystemComponent.INSTANCE;
  }

  @Override
  public CpuJiffies[] data() {
    return Arrays.copyOf(jiffies, jiffies.length);
  }

  @Override
  public String toString() {
    // TODO: temporarily using json
    return String.format(
        "{\"start\":{\"seconds\":%d,\"nanos\":%d},\"end\":{\"seconds\":%d,\"nanos\":%d},\"data\":[%s]}",
        start.getEpochSecond(),
        start.getNano(),
        end.getEpochSecond(),
        end.getNano(),
        Arrays.stream(jiffies).map(CpuJiffies::toString).collect(joining(",")));
  }

  @Override
  public int compareTo(SystemJiffies other) {
    int start = start().compareTo(other.start());
    if (start < 0) {
      return start;
    } else {
      return end().compareTo(other.end());
    }
  }
}
