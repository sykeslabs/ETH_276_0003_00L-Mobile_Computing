"""Interactive multistage-game simulator for notebook 04.4."""

def show_tit_for_tat_simulation():
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch
    from io import BytesIO
    import base64
    from ipywidgets import Dropdown, IntSlider, BoundedIntText, Button, VBox, HBox, Output, Layout
    from IPython.display import display

    levels = np.arange(16)
    rounds = 100

    def sentence_numerators(i, j):
        # Exact integers: divide by 15 to obtain years in prison.
        return np.stack((15 - i + 4*j,
                         15 + 4*i - j), axis=-1)

    # Axis 0 is A's level; axis 1 is B's level; last axis holds A/B costs.
    action_a, action_b = np.meshgrid(levels, levels, indexing='ij')
    table = sentence_numerators(action_a, action_b)
    numerators = table.reshape(-1, 2)
    outcomes = numerators / 15.0

    # A point is efficient if no other feasible point dominates it (costs minimized).
    pareto_mask = np.array([
        not np.any(np.all(numerators <= point, axis=1)
                   & np.any(numerators < point, axis=1))
        for point in numerators
    ])
    # Check unilateral deviations: A varies rows; B varies columns.
    nash_mask = ((table[:, :, 0] == table[:, :, 0].min(axis=0, keepdims=True))
                 & (table[:, :, 1] == table[:, :, 1].min(axis=1, keepdims=True)))
    nash_outcomes = table[nash_mask] / 15.0

    def choose_level(strategy, fixed, previous_self, previous_other, rng):
        if strategy == 'Always cooperate':
            return 0
        if strategy == 'Always defect':
            return 15
        if strategy == 'Fixed level':
            return fixed
        if strategy == 'Random':
            return int(rng.integers(0, 16))
        if strategy == 'Tit-for-Tat':
            # Match greater informing; otherwise initiate one cooperative step.
            if previous_other > previous_self:
                return previous_other
            return max(0, previous_self - 1)
        raise ValueError(f'Unknown strategy: {strategy}')

    def simulate(strategy_a, strategy_b, fixed_a=7, fixed_b=7, seed=7):
        # Separate streams keep each player's random sequence stable across comparisons.
        stream_a, stream_b = np.random.SeedSequence(seed).spawn(2)
        rng_a, rng_b = np.random.default_rng(stream_a), np.random.default_rng(stream_b)
        actions = np.empty((rounds, 2), dtype=int)
        previous_a = previous_b = 15
        for t in range(rounds):
            i = choose_level(strategy_a, fixed_a, previous_a, previous_b, rng_a)
            j = choose_level(strategy_b, fixed_b, previous_b, previous_a, rng_b)
            # Initialize every strategy pairing at the one-round Nash equilibrium.
            if t == 0:
                i = j = 15
            actions[t] = (i, j)
            previous_a, previous_b = i, j
        costs = sentence_numerators(actions[:, 0], actions[:, 1]) / 15.0
        return actions, costs

    strategies = ['Always cooperate', 'Always defect', 'Fixed level', 'Random', 'Tit-for-Tat']
    w_a = Dropdown(options=strategies, value='Random', description='Prisoner A:',
                   layout=Layout(width='300px'))
    w_b = Dropdown(options=strategies, value='Random', description='Prisoner B:',
                   layout=Layout(width='300px'))
    fixed_a = IntSlider(min=0, max=15, value=7, description='A fixed level:',
                        continuous_update=False, disabled=True)
    fixed_b = IntSlider(min=0, max=15, value=7, description='B fixed level:',
                        continuous_update=False, disabled=True)
    seed = BoundedIntText(value=7, min=0, max=2147483647, description='Seed:', layout=Layout(width='180px'))
    new_run = Button(description='Run')
    through = IntSlider(min=1, max=rounds, value=10, description='Show through round:',
                        style={'description_width': '140px'},
                        layout=Layout(width='620px'), continuous_update=False)
    out = Output()
    state = {}
    path_color = '#2563eb'

    def render(*_):
        end = through.value
        path = state['costs'][:end]
        with plt.ioff():
            fig, ax = plt.subplots(figsize=(8, 8))

        ax.scatter(outcomes[:, 0], outcomes[:, 1], s=18, color='#94a3b8', alpha=0.55,
                   label='All 256 outcomes', zorder=1)
        ax.plot([0, 5.5], [0, 5.5], color='#6b7280', linewidth=1.3,
                linestyle='--', label='Equal Outcomes', zorder=0.8)
        efficient = outcomes[pareto_mask]
        efficient = efficient[np.argsort(efficient[:, 0])]
        ax.plot(efficient[:, 0], efficient[:, 1], color='#15803d', linewidth=1.5,
                linestyle='-', marker='o', markersize=5.7, markerfacecolor='white',
                markeredgewidth=1.4, label='Pareto Frontier', zorder=3)

        # Drawing randomness is independent of player choices and stable across slider changes.
        visual_rng = np.random.default_rng(np.random.SeedSequence([seed.value, 9441]))
        bends = visual_rng.uniform(0.35, 0.65, size=rounds - 1)
        ax.plot([], [], color=path_color, linewidth=1.6, alpha=0.75,
                linestyle='-', label='Trajectory')
        for t, (start, stop) in enumerate(zip(path[:-1], path[1:])):
            distance = np.linalg.norm(stop - start)
            if distance < 1e-12:
                continue
            # The same bend sign puts reverse jumps on opposite sides of their chord.
            # Limit the bow to about 0.22 years so arcs remain near their endpoints.
            bend = min(bends[t], 0.44 / distance)
            jump = FancyArrowPatch(start, stop, connectionstyle=f'arc3,rad={bend}',
                                   arrowstyle='-|>', mutation_scale=10,
                                   shrinkA=0, shrinkB=0, color=path_color,
                                   linewidth=1.6, alpha=0.75, zorder=4)
            ax.add_patch(jump)

        ax.scatter(nash_outcomes[:, 0], nash_outcomes[:, 1], s=100, color='#dc2626',
                   marker='D', edgecolors='white', label='1-round NE', zorder=7)
        ax.scatter(*path[0], s=150, marker='o', facecolors='none', edgecolors=path_color,
                   linewidths=1.8, label='First Round', zorder=8)
        ax.scatter(*path[-1], s=110, marker='X', color=path_color, edgecolors='white',
                   label='Last Round', zorder=9)
        last_a, last_b = path[-1]
        label_left = last_a >= 3
        label_above = last_b < 1 or np.allclose(path[-1], (4, 4))
        ax.annotate(f'({last_a:.2f}, {last_b:.2f})', xy=path[-1],
                    xytext=(-12 if label_left else 12, 14 if label_above else -16),
                    textcoords='offset points', ha='right' if label_left else 'left',
                    va='bottom' if label_above else 'top', color=path_color, fontsize=12,
                    zorder=11,
                    bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': 0.9, 'pad': 1},
                    arrowprops={'arrowstyle': '-', 'color': path_color, 'lw': 0.8,
                                'shrinkA': 2, 'shrinkB': 5})
        ax.scatter(1, 1, s=58, facecolors='white', edgecolors='#15803d',
                   linewidths=1.8, zorder=6)
        ax.annotate('(1, 1)', xy=(1, 1), xytext=(-18, -18), textcoords='offset points',
                    ha='right', va='top', color='#166534', fontsize=12, zorder=10,
                    bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': 0.9, 'pad': 1},
                    arrowprops={'arrowstyle': '-', 'color': '#166534', 'lw': 0.8,
                                'shrinkA': 2, 'shrinkB': 5})
        ax.annotate('(4, 4)', xy=(4, 4), xytext=(8, -14), textcoords='offset points',
                    color='#b91c1c', fontsize=12)
        ax.set_xlabel('Prisoner A - years in prison', fontsize=14)
        ax.set_ylabel('Prisoner B - years in prison', fontsize=14)
        ax.set_xlim(-0.25, 5.75)
        ax.set_ylim(-0.25, 5.75)
        ax.set_aspect('equal', adjustable='box')
        ax.set_xticks(range(6))
        ax.set_yticks(range(6))
        ax.tick_params(axis='both', labelsize=12)
        ax.grid(alpha=0.3)
        ax.set_axisbelow(True)
        ax.legend(loc='upper right', ncol=2, fontsize=11, framealpha=0.95,
                  handlelength=2, columnspacing=1.2, labelspacing=0.4)
        fig.tight_layout()

        try:
            with BytesIO() as buffer:
                fig.savefig(buffer, format='png', bbox_inches='tight')
                image_data = base64.b64encode(buffer.getvalue()).decode('ascii')
        finally:
            plt.close(fig)
        out.outputs = ({'output_type': 'display_data', 'data': {'image/png': image_data},
                        'metadata': {}},)

    def rerun(*_):
        fixed_a.disabled = w_a.value != 'Fixed level'
        fixed_b.disabled = w_b.value != 'Fixed level'
        actions, costs = simulate(w_a.value, w_b.value, fixed_a.value, fixed_b.value,
                                  seed.value)
        state.update(actions=actions, costs=costs)
        render()

    for control in (w_a, w_b, fixed_a, fixed_b, seed):
        control.observe(rerun, names='value')
    through.observe(render, names='value')
    new_run.on_click(lambda _: setattr(seed, 'value', seed.value + 1))
    rerun()
    display(VBox([HBox([w_a, w_b]), HBox([fixed_a, fixed_b]),
                  HBox([seed, new_run]), through, out]))
    return {'simulate': simulate, 'sentence_numerators': sentence_numerators,
            'outcomes': outcomes, 'pareto_mask': pareto_mask, 'nash_mask': nash_mask,
            'state': state, 'output': out,
            'controls': {'a': w_a, 'b': w_b, 'fixed_a': fixed_a, 'fixed_b': fixed_b,
                         'seed': seed, 'through': through, 'new_run': new_run}}


if __name__ == "__main__":
    repeated_game_ui = show_tit_for_tat_simulation()
