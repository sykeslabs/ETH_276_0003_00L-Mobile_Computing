"""Compare current-session Pi measurements within their respective workloads."""
from html import escape
import math
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import HTML, display

COLORS = {'CPU': '#3978a8', 'GPU': '#d88b38', 'NPU': '#309886'}


def table(headers, rows):
    head = ''.join(f'<th style="font-weight:normal;text-align:left;padding:9px">{escape(h)}</th>' for h in headers)
    body = ''.join('<tr>'+''.join(f'<td style="padding:8px;border-bottom:1px solid #ddd">{escape(str(v))}</td>' for v in row)+'</tr>' for row in rows)
    display(HTML(f'<table style="width:100%;border-collapse:collapse"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'))


def chart(title, subtitle, labels, values, processors, unit):
    fig, ax = plt.subplots(figsize=(10, max(2.6, len(labels)*.48+1.3)), layout='constrained')
    fig.patch.set_facecolor('#faf9f5')
    ax.set_facecolor('#faf9f5')
    y = np.arange(len(labels))
    ax.barh(y, values, height=.52, color=[COLORS[p] for p in processors], zorder=3)
    ax.set_yticks(y, labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, max(values)*1.24)
    for i, v in enumerate(values):
        ax.annotate(f'{v:,.2f} {unit}', (v,i), xytext=(7,0), textcoords='offset points', va='center', fontsize=10, color='#263444')
    ax.set_title(title+'\n'+subtitle, loc='left', fontsize=12, pad=18, color='#263444')
    ax.set_xlabel(f'Time ({unit}) · shorter is faster', fontsize=10, color='#526171')
    ax.xaxis.grid(True, color='#e3e5e6', zorder=0)
    ax.tick_params(axis='both', length=0, colors='#526171', pad=8)
    for spine in ax.spines.values(): spine.set_visible(False)
    display(fig)
    plt.close(fig)


def show_comparison(matrix=None, neural=None, llm=None):
    display(HTML('<p><span style="color:#3978a8">● CPU</span> &nbsp; <span style="color:#d88b38">● GPU</span> &nbsp; <span style="color:#309886">● NPU</span></p>'))
    runs = (matrix or {}).get('results', [])
    if runs:
        keys = {(r['host'],r['n'],r['dtype'],r['boundary'],r['input_sha256']) for r in runs}
        if len(keys)!=1 or any(not r.get('validated') for r in runs):
            raise ValueError('Matrix results must be validated and share the same workload.')
        times = [sum(r['trial_s'])/len(r['trial_s'])/r['repetitions'] for r in runs]
        if any(not math.isfinite(t) or t<=0 for t in times): raise ValueError('Invalid matrix timing')
        chart('Matrix multiplication', f"{runs[0]['n']} × {runs[0]['n']} · {runs[0]['dtype']} · prepared buffers", [r['implementation'].replace(' / ','\n') for r in runs], [t*1000 for t in times], [r['processor'] for r in runs], 'ms')
        table(['Implementation','Time (ms)','Matrix multiplications/s','GOP/s'], [[r['implementation'],f'{t*1000:.3f}',f'{1/t:.2f}',f'{2*r["n"]**3/t/1e9:.2f}'] for r,t in zip(runs,times)])
    else: print('Matrix results unavailable. Run section 3.1.')
    runs = (neural or {}).get('results', [])
    if runs:
        if len({(r['input_sha256'],r['model'],r['batch_size']) for r in runs})!=1 or any(not r['output_checks_passed'] for r in runs):
            raise ValueError('ResNet results must share validated input and model.')
        chart('ResNet-50 image classification', 'Same image · CPU/GPU FP32 · NPU quantized', [r['implementation'] for r in runs], [r['average_ms'] for r in runs], [r['processor'] for r in runs], 'ms')
        table(['Implementation','Precision','Time (ms)','Inferences/s','Top class'], [[r['implementation'],r['precision'],f'{r["average_ms"]:.3f}',f'{r["inferences_per_s"]:.2f}',r['top1']] for r in runs])
    else: print('ResNet-50 results unavailable. Run section 3.2.')
    backends = (llm or {}).get('backends', [])
    if backends:
        labels, values, processors, rows = [], [], [], []
        for prompt in llm['prompts']:
            for backend in backends:
                r = next((r for r in backend['runs'] if r['prompt_id']==prompt['id'] and r['repetition']==1), None)
                name=backend['processor']
                if r is None:
                    rows.append([prompt['id'],name,'Unavailable','Unavailable','Unavailable','Unavailable'])
                    continue
                labels.append(f"{prompt['id']} · {name}");values.append(r['total_s']);processors.append(name)
                rows.append([prompt['id'],name,f'{r["time_to_first_text_s"]:.3f}',f'{r["total_s"]:.3f}',r['output_tokens'],f'{r["output_tokens"]/r["total_s"]:.2f}'])
        if values:
            chart('Qwen2 language generation', 'One measured response per prompt and processor · response lengths can differ', labels, values, processors, 's')
        table(['Prompt','Processor','First text (s)','Response (s)','Output tokens','Tokens/s incl. prompt'], rows)
    else: print('Qwen2 results unavailable. Run section 3.3.')
