#include "include/cpu_meter.hh"

namespace MSys {

namespace Detail {

static const char *core_stat_format =
    "%*s "  // (1)  [NT] cpu %s (in format of "cpu\d*")
    "%lu "  // (2)  [1]  user %llu
    "%lu "  // (3)  [2]  nice %llu
    "%lu "  // (4)  [3]  system %llu
    "%lu "  // (5)  [4]  idle %llu
    "%lu "  // (6)  [5]  iowait %llu
    "%lu "  // (7)  [6]  irq %llu
    "%lu "  // (8)  [7]  softirq %llu
    "%lu "  // (9)  [8]  steal %llu
    "%lu "  // (10) [9]  guest %llu
    "%lu "  // (11) [10] guest_nice %llu
    ;

static const char *kernel_misc_stat_format =
    "intr %lu %*[^\n] "  // (1) [1, NT] intr %lu
    "ctxt %lu "          // (2) [2]     ctxt %lu
    "btime %*lu "        // (3) [NT]    btime %lu
    "processes %lu "     // (4) [3]     processes %lu
    "procs_running %u "  // (5) [4]     procs_running %u
    "procs_blocked %u "  // (6) [5]     procs_blocked %u
    ;

static const char *softirq_stat_format =
    "softirq "  // (1)  [NT] softirq %s
    "%lu "      // (2)  [1]  total %lu
    "%lu "      // (3)  [2]  hi %lu
    "%lu "      // (4)  [3]  timer %lu
    "%lu "      // (5)  [4]  net_tx %lu
    "%lu "      // (6)  [5]  net_rx %lu
    "%lu "      // (7)  [6]  block %lu
    "%lu "      // (8)  [7]  irq_poll %lu
    "%lu "      // (9)  [8]  tasklet %lu
    "%lu "      // (10) [9]  sched %lu
    "%lu "      // (11) [10] hrtimer %lu
    "%lu "      // (12) [11] rcu %lu
    ;

static inline bool parseProcStat(unsigned ncores, CPUMetrics *metrics) {
    FILE *fp = fopen(PROCSTATFILE, "r");

    if (unlikely(!fp)) {
        LOG(ERROR) << absl::StrFormat(
            "[CPUMeter] Failed to open %s: %s", PROCSTATFILE, strerror(errno));
        return false;
    }

    // time stamp
    metrics->set_timestamp(cr::steady_clock::now().time_since_epoch().count());

    bool ret = true;
    // Core stats
    {
        unsigned long user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice;
        for (unsigned core_stat_idx = 0; core_stat_idx < ncores + 1; core_stat_idx++) {
            CoreStat *core_stat = metrics->add_core_stats();
            int nfields = fscanf(
                fp, core_stat_format, &user, &nice, &system, &idle, &iowait, &irq, &softirq, &steal,
                &guest, &guest_nice);
            if (unlikely(nfields < 10)) {
                // If we don't have all fields, we can still proceed with the available
                // ones.
                LOG(WARNING) << absl::StrFormat(
                    "[CPUMeter] Expected 10 fields in /proc/stat for core %u, got %d. "
                    "Some metrics may be missing.",
                    core_stat_idx - 1, nfields);
                ret = false;
            }
            core_stat->set_user(user);
            core_stat->set_nice(nice);
            core_stat->set_system(system);
            core_stat->set_idle(idle);
            core_stat->set_iowait(iowait);
            core_stat->set_irq(irq);
            core_stat->set_softirq(softirq);
            core_stat->set_steal(steal);
            core_stat->set_guest(guest);
            core_stat->set_guest_nice(guest_nice);
        }
    }

    // Kernel misc stats
    {
        KernelMiscStat *misc_stat = metrics->mutable_kernel_misc_stat();
        unsigned long intr, ctxt, processes;
        unsigned procs_running, procs_blocked;

        int nfields = fscanf(
            fp, kernel_misc_stat_format, &intr, &ctxt, &processes, &procs_running, &procs_blocked);
        if (unlikely(nfields < 5)) {
            // If we don't have all fields, we can still proceed with the available
            // ones.
            LOG(WARNING) << absl::StrFormat(
                "[CPUMeter] Expected 5 fields in /proc/stat, got %d. "
                "Some metrics may be missing.",
                nfields);
            ret = false;
        }
        misc_stat->set_intr(intr);
        misc_stat->set_ctxt(ctxt);
        misc_stat->set_processes(processes);
        misc_stat->set_procs_running(procs_running);
        misc_stat->set_procs_blocked(procs_blocked);
    }

    // SoftIRQ stats
    {
        SoftIRQStat *softirq_stat = metrics->mutable_soft_irq_stat();
        unsigned long total, hi, timer, net_tx, net_rx, block, irq_poll, tasklet, sched, hrtimer,
            rcu;

        int nfields = fscanf(
            fp, softirq_stat_format, &total, &hi, &timer, &net_tx, &net_rx, &block, &irq_poll,
            &tasklet, &sched, &hrtimer, &rcu);
        if (unlikely(nfields < 11)) {
            // If we don't have all fields, we can still proceed with the available
            // ones.
            LOG(WARNING) << absl::StrFormat(
                "[CPUMeter] Expected 11 fields in /proc/softirqs, got %d. "
                "Some metrics may be missing.",
                nfields);
            ret = false;
        }
        softirq_stat->set_total(total);
        softirq_stat->set_hi(hi);
        softirq_stat->set_timer(timer);
        softirq_stat->set_net_tx(net_tx);
        softirq_stat->set_net_rx(net_rx);
        softirq_stat->set_block(block);
        softirq_stat->set_irq_poll(irq_poll);
        softirq_stat->set_tasklet(tasklet);
        softirq_stat->set_sched(sched);
        softirq_stat->set_hrtimer(hrtimer);
        softirq_stat->set_rcu(rcu);
    }

    fclose(fp);
    return ret;
}

}  // namespace Detail

CPUMeter::CPUMeter(cr::milliseconds tick_period)
    : Meter("CPUMeter", tick_period, [] { return new CPUMetricsTimeSeries(); }),
      ncores(getSystemNProc()) {
    markValid();
}

bool CPUMeter::update(bool testrun) {
    UNUSED(testrun);

    CPUMetrics *cpu_metrics = getCurrentBuffer<CPUMetricsTimeSeries>()->add_metrics();
    return Detail::parseProcStat(ncores, cpu_metrics);
}

std::string CPUMeter::getDetailedReport() const {
    std::string report;
    report += absl::StrFormat("Number of CPU cores: %u\n", ncores);
    return report;
}

}  // namespace MSys
