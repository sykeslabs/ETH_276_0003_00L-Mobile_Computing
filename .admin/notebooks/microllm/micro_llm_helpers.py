from html import escape
import json
import math
from pathlib import Path
import random

from IPython.display import HTML, display


class Value:
    __slots__ = ('data', 'grad', '_children', '_local_grads')

    def __init__(self, data, children=(), local_grads=()):
        self.data = data
        self.grad = 0
        self._children = children
        self._local_grads = local_grads

    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data + other.data, (self, other), (1, 1))

    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data * other.data, (self, other), (other.data, self.data))

    def __pow__(self, other):
        return Value(self.data ** other, (self,), (other * self.data ** (other - 1),))

    def log(self):
        return Value(math.log(self.data), (self,), (1 / self.data,))

    def exp(self):
        return Value(math.exp(self.data), (self,), (math.exp(self.data),))

    def relu(self):
        return Value(max(0, self.data), (self,), (float(self.data > 0),))

    def __neg__(self):
        return self * -1

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, other):
        return other + (-self)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        return self * other ** -1

    def __rtruediv__(self, other):
        return other * self ** -1

    def backward(self):
        topo = []
        visited = set()

        def build_topo(v):
            if v not in visited:
                visited.add(v)
                for child in v._children:
                    build_topo(child)
                topo.append(v)

        build_topo(self)
        self.grad = 1
        for v in reversed(topo):
            for child, local_grad in zip(v._children, v._local_grads):
                child.grad += local_grad * v.grad


def initialize_microllm_state(seed=2, n_layer=1, n_embd=16, block_size=16, n_head=4):
    import random
    import re

    from micro_llm_training_data import get_training_examples

    random.seed(seed)
    training_examples = get_training_examples(seed=seed)
    word_re = re.compile(r"[a-z]+(?:'[a-z]+)?")

    def split_into_words(text):
        return word_re.findall(text.lower())

    id_to_token = sorted({word for ex in training_examples for word in split_into_words(ex)})
    token_to_id = {tok: i for i, tok in enumerate(id_to_token)}
    bos_token_id = len(id_to_token)
    vocab_size = len(id_to_token) + 1

    def encode(text):
        return [token_to_id[word] for word in split_into_words(text)]

    def decode(token_ids):
        return ' '.join(id_to_token[token_id] for token_id in token_ids)

    head_dim = n_embd // n_head

    def matrix(nout, nin, std=0.08):
        return [[Value(random.gauss(0, std)) for _ in range(nin)] for _ in range(nout)]

    state_dict = {
        'wte': matrix(vocab_size, n_embd),
        'wpe': matrix(block_size, n_embd),
        'lm_head': matrix(vocab_size, n_embd),
    }

    for i in range(n_layer):
        state_dict[f'layer{i}.attn_wq'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.attn_wk'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.attn_wv'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.attn_wo'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.mlp_fc1'] = matrix(4 * n_embd, n_embd)
        state_dict[f'layer{i}.mlp_fc2'] = matrix(n_embd, 4 * n_embd)

    params = [p for mat in state_dict.values() for row in mat for p in row]

    return {
        'training_examples': training_examples,
        'split_into_words': split_into_words,
        'id_to_token': id_to_token,
        'token_to_id': token_to_id,
        'BOS': bos_token_id,
        'vocab_size': vocab_size,
        'encode': encode,
        'decode': decode,
        'n_layer': n_layer,
        'n_embd': n_embd,
        'block_size': block_size,
        'n_head': n_head,
        'head_dim': head_dim,
        'state_dict': state_dict,
        'params': params,
    }


MICROLLM_INITIAL_STATE_PATH = Path('microllm_step1_initial_state.json')
MICROLLM_TRAINED_STATE_PATH = Path('microllm_step2_trained_state.json')


def _state_dict_to_data(state_dict):
    return {
        name: [[value.data for value in row] for row in matrix]
        for name, matrix in state_dict.items()
    }


def _data_to_state_dict(state_data):
    return {
        name: [[Value(value) for value in row] for row in matrix]
        for name, matrix in state_data.items()
    }


def save_microllm_state(path, state, training_log=None):
    payload = {
        'training_examples': state['training_examples'],
        'id_to_token': state['id_to_token'],
        'bos_token_id': state['BOS'],
        'n_layer': state['n_layer'],
        'n_embd': state['n_embd'],
        'block_size': state['block_size'],
        'n_head': state['n_head'],
        'head_dim': state['head_dim'],
        'state_dict': _state_dict_to_data(state['state_dict']),
        'training_log': training_log or [],
    }
    path = Path(path)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return path


def load_microllm_state(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f'Missing {path}. Run the previous MicroLLM step notebook first to create it.'
        )

    payload = json.loads(path.read_text(encoding='utf-8'))
    training_examples = payload['training_examples']
    id_to_token = payload['id_to_token']
    token_to_id = {token: i for i, token in enumerate(id_to_token)}
    bos_token_id = payload['bos_token_id']
    state_dict = _data_to_state_dict(payload['state_dict'])
    params = [p for mat in state_dict.values() for row in mat for p in row]

    import re

    word_re = re.compile(r"[a-z]+(?:'[a-z]+)?")

    def split_into_words(text):
        return word_re.findall(text.lower())

    def encode(text):
        return [token_to_id[word] for word in split_into_words(text)]

    def decode(token_ids):
        return ' '.join(id_to_token[token_id] for token_id in token_ids)

    return {
        'training_examples': training_examples,
        'split_into_words': split_into_words,
        'id_to_token': id_to_token,
        'token_to_id': token_to_id,
        'BOS': bos_token_id,
        'vocab_size': len(id_to_token) + 1,
        'encode': encode,
        'decode': decode,
        'n_layer': payload['n_layer'],
        'n_embd': payload['n_embd'],
        'block_size': payload['block_size'],
        'n_head': payload['n_head'],
        'head_dim': payload['head_dim'],
        'state_dict': state_dict,
        'params': params,
        'training_log': [tuple(item) for item in payload.get('training_log', [])],
    }


def linear(x, w):
    return [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w]


def softmax(logits):
    max_val = max(val.data for val in logits)
    exps = [(val - max_val).exp() for val in logits]
    total = sum(exps)
    return [e / total for e in exps]


def rmsnorm(x):
    ms = sum(xi * xi for xi in x) / len(x)
    scale = (ms + 1e-5) ** -0.5
    return [xi * scale for xi in x]


def make_gpt_forward(state_dict, n_layer, n_head, head_dim):
    def gpt_forward(token_id, pos_id, keys, values):
        tok_emb = state_dict['wte'][token_id]
        pos_emb = state_dict['wpe'][pos_id]
        x = [t + p for t, p in zip(tok_emb, pos_emb)]
        x = rmsnorm(x)

        for li in range(n_layer):
            x_residual = x
            x = rmsnorm(x)
            q = linear(x, state_dict[f'layer{li}.attn_wq'])
            k = linear(x, state_dict[f'layer{li}.attn_wk'])
            v = linear(x, state_dict[f'layer{li}.attn_wv'])
            keys[li].append(k)
            values[li].append(v)

            x_attn = []
            for h in range(n_head):
                hs = h * head_dim
                q_h = q[hs:hs + head_dim]
                k_h = [ki[hs:hs + head_dim] for ki in keys[li]]
                v_h = [vi[hs:hs + head_dim] for vi in values[li]]
                attn_logits = [
                    sum(q_h[j] * k_h[t][j] for j in range(head_dim)) / head_dim ** 0.5
                    for t in range(len(k_h))
                ]
                attn_weights = softmax(attn_logits)
                head_out = [
                    sum(attn_weights[t] * v_h[t][j] for t in range(len(v_h)))
                    for j in range(head_dim)
                ]
                x_attn.extend(head_out)

            x = linear(x_attn, state_dict[f'layer{li}.attn_wo'])
            x = [a + b for a, b in zip(x, x_residual)]

            x_residual = x
            x = rmsnorm(x)
            x = linear(x, state_dict[f'layer{li}.mlp_fc1'])
            x = [xi.relu() for xi in x]
            x = linear(x, state_dict[f'layer{li}.mlp_fc2'])
            x = [a + b for a, b in zip(x, x_residual)]

        return linear(x, state_dict['lm_head'])

    return gpt_forward


def train_microllm(
    params,
    training_examples,
    bos_token_id,
    encode,
    block_size,
    n_layer,
    gpt_forward,
    softmax_fn=softmax,
    learning_rate=0.01,
    beta1=0.85,
    beta2=0.99,
    eps_adam=1e-8,
    num_steps=300,
):
    m = [0.0] * len(params)
    v = [0.0] * len(params)
    training_log = []

    for step in range(num_steps):
        example = training_examples[step % len(training_examples)]
        tokens = [bos_token_id] + encode(example) + [bos_token_id]
        n = min(block_size, len(tokens) - 1)

        keys, values = [[] for _ in range(n_layer)], [[] for _ in range(n_layer)]
        losses = []
        for pos_id in range(n):
            token_id, target_id = tokens[pos_id], tokens[pos_id + 1]
            logits = gpt_forward(token_id, pos_id, keys, values)
            probs = softmax_fn(logits)
            losses.append(-probs[target_id].log())

        loss = (1 / n) * sum(losses)
        loss.backward()

        lr_t = learning_rate * (1 - step / num_steps)
        for i, p in enumerate(params):
            m[i] = beta1 * m[i] + (1 - beta1) * p.grad
            v[i] = beta2 * v[i] + (1 - beta2) * p.grad ** 2
            m_hat = m[i] / (1 - beta1 ** (step + 1))
            v_hat = v[i] / (1 - beta2 ** (step + 1))
            p.data -= lr_t * m_hat / (v_hat ** 0.5 + eps_adam)
            p.grad = 0

        training_log.append((step + 1, loss.data, lr_t))

    return training_log


def ensure_notebook_environment():
    import importlib.util
    import subprocess
    import sys

    required_packages = {
        'numpy': 'numpy',
        'sklearn': 'scikit-learn',
        'plotly': 'plotly',
        'ipywidgets': 'ipywidgets',
        'nbformat': 'nbformat',
    }

    missing = [
        package_name
        for import_name, package_name in required_packages.items()
        if importlib.util.find_spec(import_name) is None
    ]

    if missing:
        print('Installing missing packages:', ', '.join(missing))
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])
    else:
        print('All required packages are already installed.')


PARAMETER_DESCRIPTIONS = {
    'wte': 'Token embedding matrix: maps each token ID to its learned vector.',
    'wpe': 'Position embedding matrix: adds information about where the token appears in the context.',
    'lm_head': 'Output layer: turns the final token representation into scores for possible next tokens.',
    'attn_wq': 'Query projection: creates the vector used to ask which earlier tokens matter.',
    'attn_wk': 'Key projection: creates the vector earlier tokens use to be matched by queries.',
    'attn_wv': 'Value projection: creates the information that is copied forward after attention weights are chosen.',
    'attn_wo': 'Attention output projection: mixes the attention-head outputs back into one embedding vector.',
    'mlp_fc1': 'First MLP layer: expands the token representation before the nonlinearity.',
    'mlp_fc2': 'Second MLP layer: compresses the MLP output back to the embedding size.',
}


def show_parameter_table(state_dict):
    table = [
        '<table style="border-collapse: collapse; width: 100%;">',
        '<colgroup>',
        '<col style="width: 20%;">',
        '<col style="width: 45%;">',
        '<col style="width: 18%;">',
        '<col style="width: 17%;">',
        '</colgroup>',
        '<thead><tr><th>parameter group</th><th>represents</th><th>shape</th><th>trainable values</th></tr></thead>',
        '<tbody>',
    ]
    total = 0
    for name, mat in state_dict.items():
        rows = len(mat)
        cols = len(mat[0]) if rows else 0
        count = rows * cols
        total += count
        key = name.split('.')[-1]
        description = PARAMETER_DESCRIPTIONS.get(key, 'Learnable weight matrix used by the model.')
        table.append(
            '<tr>'
            f'<td><code>{escape(name)}</code></td>'
            f'<td>{escape(description)}</td>'
            f'<td style="white-space: nowrap; text-align: right;"><strong>{rows} x {cols}</strong></td>'
            f'<td style="text-align: right;">{count}</td>'
            '</tr>'
        )
    table.append(
        f'<tr><td><strong>total</strong></td><td></td><td></td>'
        f'<td style="text-align: right;"><strong>{total}</strong></td></tr>'
    )
    table.append('</tbody></table>')
    display(HTML('\n'.join(table)))


def _interpolate_color(left, right, t):
    return tuple(round(left[i] + (right[i] - left[i]) * t) for i in range(3))


def _value_to_color(value):
    value = max(-1.0, min(1.0, value))
    blue = (33, 102, 172)
    white = (247, 247, 247)
    red = (178, 24, 43)
    if value < 0:
        rgb = _interpolate_color(blue, white, value + 1)
    else:
        rgb = _interpolate_color(white, red, value)
    return f'rgb({rgb[0]}, {rgb[1]}, {rgb[2]})'


def _matrix_svg(mat, cell_size=4):
    rows = len(mat)
    cols = len(mat[0]) if rows else 0
    width = cols * cell_size
    height = rows * cell_size
    rects = []
    for r, matrix_row in enumerate(mat):
        for c, value in enumerate(matrix_row):
            rects.append(
                f'<rect x="{c * cell_size}" y="{r * cell_size}" '
                f'width="{cell_size}" height="{cell_size}" fill="{_value_to_color(value.data)}" />'
            )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'preserveAspectRatio="none" style="width: 100%; height: 100%; display: block; image-rendering: pixelated;">'
        + ''.join(rects)
        + '</svg>'
    )


def _matrix_card(name, mat):
    rows = len(mat)
    cols = len(mat[0]) if rows else 0
    aspect = cols / rows if rows else 1
    if aspect < 0.45:
        box_style = 'width: 64px; height: 180px;'
    elif aspect > 2.2:
        box_style = 'width: 180px; height: 64px;'
    else:
        box_style = 'width: 128px; height: 128px;'

    return f'''
    <div style="border: 1px solid #e5e7eb; padding: 8px; background: white;">
      <div style="font-family: var(--jp-code-font-family, monospace); font-size: 12px; line-height: 1.2; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{escape(name)}">
        {escape(name)}
      </div>
      <div style="font-size: 11px; color: #555; margin-bottom: 8px;">{rows} x {cols}</div>
      <div style="{box_style} margin: 0 auto; border: 1px solid #eef0f2; background: #fafafa;">
        {_matrix_svg(mat)}
      </div>
    </div>
    '''


def show_parameter_heatmaps(state_dict):
    cards = '\n'.join(_matrix_card(name, mat) for name, mat in state_dict.items())
    legend = '''
    <div style="display: grid; grid-template-columns: auto 220px auto; align-items: center; gap: 8px; max-width: 360px; margin: 0.75em 0 1em 0; font-size: 12px; color: #333;">
      <span>-1</span>
      <div style="height: 12px; background: linear-gradient(90deg, rgb(33,102,172), rgb(247,247,247), rgb(178,24,43)); border: 1px solid #d1d5db;"></div>
      <span>+1</span>
      <div></div><div style="display: flex; justify-content: space-between;"><span>negative</span><span>zero</span><span>positive</span></div><div></div>
    </div>
    '''
    html = f'''
    <div>
      {legend}
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; align-items: start;">
        {cards}
      </div>
    </div>
    '''
    display(HTML(html))


def show_training_log(training_log, num_steps, num_params):
    if not training_log:
        display(HTML('<p>No training log entries yet.</p>'))
        return

    first_step, first_loss, _ = training_log[0]
    last_step, last_loss, last_lr = training_log[-1]
    recent = training_log[-5:]

    losses = [loss for _, loss, _ in training_log]
    min_loss = min(losses)
    max_loss = max(losses)
    loss_span = max_loss - min_loss or 1.0
    width = 620
    height = 180
    pad_left = 44
    pad_right = 16
    pad_top = 18
    pad_bottom = 34
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    points = []
    for step, loss, _ in training_log:
        x = pad_left + (step - 1) / max(1, num_steps - 1) * plot_w
        y = pad_top + (max_loss - loss) / loss_span * plot_h
        points.append((x, y))

    polyline = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
    circles = ''.join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#2563eb" />'
        for x, y in points[::max(1, len(points) // 60)]
    )
    summary = f'''
    <div style="display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; margin: 0.75em 0;">
      <div style="border: 1px solid #e5e7eb; padding: 10px; background: #fff;"><div style="font-size: 12px; color: #555;">training steps</div><div style="font-size: 20px; font-weight: 700;">{num_steps}</div></div>
      <div style="border: 1px solid #e5e7eb; padding: 10px; background: #fff;"><div style="font-size: 12px; color: #555;">trainable values</div><div style="font-size: 20px; font-weight: 700;">{num_params}</div></div>
      <div style="border: 1px solid #e5e7eb; padding: 10px; background: #fff;"><div style="font-size: 12px; color: #555;">first logged loss</div><div style="font-size: 20px; font-weight: 700;">{first_loss:.4f}</div><div style="font-size: 11px; color: #666;">step {first_step}</div></div>
      <div style="border: 1px solid #e5e7eb; padding: 10px; background: #fff;"><div style="font-size: 12px; color: #555;">final logged loss</div><div style="font-size: 20px; font-weight: 700;">{last_loss:.4f}</div><div style="font-size: 11px; color: #666;">lr {last_lr:.6f}</div></div>
    </div>
    '''

    rows = ''.join(
        '<tr>'
        f'<td style="text-align: right;">{step}</td>'
        f'<td style="text-align: right;">{loss:.4f}</td>'
        f'<td style="text-align: right;">{lr:.6f}</td>'
        '</tr>'
        for step, loss, lr in recent
    )
    table = f'''
    <table style="border-collapse: collapse; width: 100%; max-width: 620px; margin-top: 0.75em;">
      <thead><tr><th style="text-align: right;">recent step</th><th style="text-align: right;">loss</th><th style="text-align: right;">learning rate (lr)</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    '''

    svg = f'''
    <svg viewBox="0 0 {width} {height}" style="width: 100%; max-width: {width}px; height: auto; display: block; background: #fff; border: 1px solid #e5e7eb;">
      <line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" y2="{height - pad_bottom}" stroke="#9ca3af" />
      <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#9ca3af" />
      <text x="8" y="{pad_top + 4}" font-size="11" fill="#555">{max_loss:.2f}</text>
      <text x="8" y="{height - pad_bottom + 4}" font-size="11" fill="#555">{min_loss:.2f}</text>
      <text x="{pad_left}" y="{height - 10}" font-size="11" fill="#555">step 1</text>
      <text x="{width - pad_right - 54}" y="{height - 10}" font-size="11" fill="#555">step {num_steps}</text>
      <polyline points="{polyline}" fill="none" stroke="#2563eb" stroke-width="2.5" />
      {circles}
    </svg>
    '''

    display(HTML(f'{summary}<div style="font-weight: 600; margin: 0.75em 0 0.35em 0;">Loss over training</div>{svg}{table}'))


def _lims(a, lo=1, hi=99, pad=0.08):
    import numpy as np

    low, high = np.percentile(a, [lo, hi])
    span = high - low
    if span == 0:
        span = 1
    return (low - pad * span, high + pad * span)


def show_token_embedding_pca(state_dict, id_to_token, bos_token_id, max_tokens_to_plot=100):
    import ipywidgets as widgets
    import numpy as np
    import plotly.graph_objs as go
    from IPython.display import clear_output
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA

    plot_token_ids = list(range(min(max_tokens_to_plot, len(id_to_token)))) + [bos_token_id]
    token_labels = [id_to_token[i] if i != bos_token_id else 'BOS' for i in plot_token_ids]
    embeddings = np.array([[v.data for v in state_dict['wte'][i]] for i in plot_token_ids], dtype=float)

    pca = PCA(n_components=3)
    embeddings_3d = pca.fit_transform(embeddings)
    evr = pca.explained_variance_ratio_
    axis_titles = [f'PCA {i + 1} ({100 * evr[i]:.1f}%)' for i in range(3)]

    x_limits = _lims(embeddings_3d[:, 0])
    y_limits = _lims(embeddings_3d[:, 1])
    z_limits = _lims(embeddings_3d[:, 2])

    n_clusters = min(6, len(token_labels))
    km = KMeans(n_clusters=n_clusters, n_init='auto', random_state=0)
    clusters = km.fit_predict(embeddings_3d)

    palette = ['#2563EB', '#DC2626', '#059669', '#7C3AED', '#D97706', '#0891B2']
    colors = [palette[i % len(palette)] for i in clusters]

    bg = 'rgba(0,0,0,0)'
    grid = '#D4D4D8'
    font = '#18181B'

    highlight_picker = widgets.Dropdown(
        options=[('No highlight', None)] + [(token, token) for token in token_labels],
        value=None,
        description='Highlight:',
        layout=widgets.Layout(width='360px'),
    )
    graph_output = widgets.Output(layout={'height': '410px', 'overflow': 'hidden'})

    def make_embedding_fig(selected_token=None):
        point_colors = list(colors)
        point_sizes = [7] * len(token_labels)
        selected_idx = None

        if selected_token is not None:
            selected_idx = token_labels.index(selected_token)
            point_colors[selected_idx] = '#FACC15'
            point_sizes[selected_idx] = 15

        fig = go.Figure()
        fig.add_trace(go.Scatter3d(
            x=embeddings_3d[:, 0],
            y=embeddings_3d[:, 1],
            z=embeddings_3d[:, 2],
            mode='markers+text',
            text=token_labels,
            textposition='top center',
            marker=dict(
                size=point_sizes,
                color=point_colors,
                opacity=0.92,
                line=dict(width=1, color='#FFFFFF'),
            ),
            hovertemplate='<b>%{text}</b><br>PCA1=%{x:.3f}<br>PCA2=%{y:.3f}<br>PCA3=%{z:.3f}<extra></extra>',
            showlegend=False,
        ))

        if selected_idx is not None:
            fig.add_trace(go.Scatter3d(
                x=[embeddings_3d[selected_idx, 0]],
                y=[embeddings_3d[selected_idx, 1]],
                z=[embeddings_3d[selected_idx, 2]],
                mode='markers+text',
                text=[f'{selected_token} <-- selected'],
                textposition='middle right',
                marker=dict(size=19, color='#FACC15', line=dict(width=3, color='#111827')),
                hovertemplate='<b>%{text}</b><extra></extra>',
                showlegend=False,
            ))

        zero_line = dict(mode='lines', line=dict(width=2, color='#71717A'), showlegend=False)
        fig.add_trace(go.Scatter3d(x=[x_limits[0], x_limits[1]], y=[0, 0], z=[0, 0], **zero_line))
        fig.add_trace(go.Scatter3d(x=[0, 0], y=[y_limits[0], y_limits[1]], z=[0, 0], **zero_line))
        fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[z_limits[0], z_limits[1]], **zero_line))

        fig.update_layout(
            height=360,
            margin=dict(l=0, r=0, t=0, b=0),
            uirevision='keep',
            scene=dict(
                xaxis=dict(title=axis_titles[0], range=x_limits, backgroundcolor=bg, gridcolor=grid, color=font),
                yaxis=dict(title=axis_titles[1], range=y_limits, backgroundcolor=bg, gridcolor=grid, color=font),
                zaxis=dict(title=axis_titles[2], range=z_limits, backgroundcolor=bg, gridcolor=grid, color=font),
                camera=dict(eye=dict(x=1.25, y=1.25, z=1.0)),
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color=font),
        )
        return fig, selected_idx

    def show_embedding_graph(selected_token=None):
        with graph_output:
            clear_output(wait=True)
            fig, selected_idx = make_embedding_fig(selected_token)
            fig.show()
            if selected_idx is not None:
                token_id = plot_token_ids[selected_idx]
                coords = np.round(embeddings_3d[selected_idx], 3)
                print(f"{selected_token!r} is token id {token_id} at PCA coordinates {coords}")

    def on_highlight_change(change):
        if change['name'] == 'value':
            show_embedding_graph(change['new'])

    highlight_picker.observe(on_highlight_change, names='value')
    display(highlight_picker, graph_output)
    show_embedding_graph(highlight_picker.value)


def show_completion_widget(
    split_into_words,
    token_to_id,
    id_to_token,
    bos_token_id,
    block_size,
    n_layer,
    gpt_forward,
    softmax,
    vocab_size,
    default_prompt='mix flour',
    num_options=5,
    max_new_tokens=12,
):
    import ipywidgets as widgets

    def prompt_to_token_ids(prompt):
        words = split_into_words(prompt)
        known = [word for word in words if word in token_to_id]
        unknown = [word for word in words if word not in token_to_id]
        return [token_to_id[word] for word in known], unknown

    def sample_completion(prompt, temperature):
        prefix_ids, unknown = prompt_to_token_ids(prompt)
        visible_prefix = prefix_ids[-(block_size - 1):]
        generated = []
        completion_probability = 1.0
        tokens = [bos_token_id] + visible_prefix
        keys, values = [[] for _ in range(n_layer)], [[] for _ in range(n_layer)]
        last_probs = None

        for pos_id, token_id in enumerate(tokens[:block_size]):
            logits = gpt_forward(token_id, pos_id, keys, values)
            last_probs = softmax([logit / temperature for logit in logits])

        next_pos = len(tokens)
        while next_pos < block_size and len(generated) < max_new_tokens and last_probs is not None:
            prob_values = [prob.data for prob in last_probs]
            next_id = random.choices(range(vocab_size), weights=prob_values)[0]
            if next_id == bos_token_id:
                break
            completion_probability *= prob_values[next_id]
            generated.append(next_id)
            logits = gpt_forward(next_id, next_pos, keys, values)
            last_probs = softmax([logit / temperature for logit in logits])
            next_pos += 1

        words = [id_to_token[token_id] for token_id in prefix_ids + generated]
        return ' '.join(words), unknown, completion_probability

    def make_completion_html(prompt, temperature):
        samples = []
        seen_samples = set()
        unknown_words = set()
        attempts = 0
        max_attempts = num_options * 8
        while len(samples) < num_options and attempts < max_attempts:
            attempts += 1
            text, unknown, probability = sample_completion(prompt.strip(), temperature)
            text = text if text else '(stopped)'
            unknown_words.update(unknown)
            if text in seen_samples:
                continue
            seen_samples.add(text)
            samples.append((text, probability))

        warning = ''
        if unknown_words:
            warning = (
                '<p style="color: #9a3412; margin: 0 0 0.75em 0;">Ignored unknown word(s): <code>'
                + escape(', '.join(sorted(unknown_words)))
                + '</code></p>'
            )

        samples.sort(key=lambda item: item[1], reverse=True)
        sample_items = ''.join(
            f'<li>{escape(sample)} <span style="color:#555;">({probability:.2%})</span></li>'
            for sample, probability in samples
        )
        return f'''
        <div style="margin-top: 0.75em;">
          {warning}
          <div style="font-weight: 600; margin-bottom: 0.35em;">Completion options <span style="font-weight: 400; color: #555;">(percentage = model probability for the generated continuation)</span></div>
          <ol style="margin-top: 0;">{sample_items}</ol>
        </div>
        '''

    prompt_box = widgets.Text(
        value=default_prompt,
        placeholder='start with known words, for example: mix flour',
        description='Prompt:',
        layout=widgets.Layout(width='520px'),
        continuous_update=False,
    )
    temperature_slider = widgets.FloatSlider(
        value=0.4,
        min=0.1,
        max=1.5,
        step=0.1,
        description='Temp:',
        readout_format='.1f',
        continuous_update=False,
        layout=widgets.Layout(width='360px'),
    )
    generate_button = widgets.Button(description='Generate', button_style='primary')
    results_html = widgets.HTML()

    def update_results(_=None):
        results_html.value = make_completion_html(
            prompt_box.value,
            temperature_slider.value,
        )

    prompt_box.observe(update_results, names='value')
    generate_button.on_click(update_results)
    controls = widgets.VBox([
        prompt_box,
        temperature_slider,
        generate_button,
        results_html,
    ])

    display(controls)
    update_results()
