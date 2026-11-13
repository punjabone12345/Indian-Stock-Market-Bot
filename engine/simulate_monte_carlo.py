import numpy as np

def run_drawdown_simulation():
    print("="*75)
    print("   MONTE CARLO PROBABILITY AUDIT: 2,000 TRADES (49 MONTHS)")
    print("   Target: 1,000R Net Return | Target Max Drawdown: <= 10R")
    print("="*75)

    scenarios = [
        ("Scenario A: WinRate 45%, Win +2.5R, Loss -1.0R (E = +0.575R)", 0.45, 2.5, 1.0),
        ("Scenario B: WinRate 50%, Win +2.2R, Loss -1.0R (E = +0.600R)", 0.50, 2.2, 1.0),
        ("Scenario C: WinRate 60%, Win +1.8R, Loss -1.0R (E = +0.680R)", 0.60, 1.8, 1.0),
        ("Scenario D: WinRate 70%, Win +1.4R, Loss -1.0R (E = +0.680R)", 0.70, 1.4, 1.0),
        ("Scenario E: WinRate 80%, Win +1.2R, Loss -1.0R (E = +0.760R)", 0.80, 1.2, 1.0),
        ("Scenario F: Breakeven Scratches (Loss -0.4R avg, Win +2.0R, WinRate 50%, E = +0.80R)", 0.50, 2.0, 0.4),
    ]

    np.random.seed(42)
    n_sims = 10000
    n_trades = 2000

    for name, wr, win_r, loss_r in scenarios:
        dd_list = []
        tot_r_list = []
        under_10_dd_count = 0

        for _ in range(n_sims):
            # Generate trades
            outcomes = np.random.rand(n_trades) < wr
            r_series = np.where(outcomes, win_r, -loss_r)
            cum = np.cumsum(r_series)
            peak = np.maximum.accumulate(cum)
            dd = peak - cum
            max_dd = np.max(dd)

            dd_list.append(max_dd)
            tot_r_list.append(cum[-1])
            if max_dd <= 10.0:
                under_10_dd_count += 0.0001 * 100 # percentage

        avg_dd = np.mean(dd_list)
        worst_dd = np.percentile(dd_list, 95)
        avg_tot_r = np.mean(tot_r_list)
        prob_under_10 = (np.array(dd_list) <= 10.0).mean() * 100

        print(f"\n{name}")
        print(f"  Average Total Return: +{avg_tot_r:.1f}R (Monthly: +{avg_tot_r/49:.1f}R/m)")
        print(f"  Expected Max Drawdown: {avg_dd:.1f}R  (95th Percentile DD: {worst_dd:.1f}R)")
        print(f"  Probability of Max DD <= 10R: {prob_under_10:.2f}%")

if __name__ == '__main__':
    run_drawdown_simulation()
