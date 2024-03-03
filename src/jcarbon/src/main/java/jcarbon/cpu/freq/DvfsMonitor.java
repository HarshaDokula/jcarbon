package jcarbon.cpu.freq;

import static jcarbon.util.LoggerUtil.getLogger;

import java.util.logging.Logger;

/** Very simple energy monitor that reports energy consumption over 10 millisecond intervals. */
final class DvfsMonitor {
  private static final Logger logger = getLogger();

  public static void main(String[] args) throws Exception {
    while (true) {
      Thread.sleep(10);
      logger.info(String.format("%s", DvfsReader.sample()));
    }
  }
}