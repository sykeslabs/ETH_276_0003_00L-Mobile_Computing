"""Extend entropy examples to 4096 symbols and plot lagged correlations."""
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
NOTEBOOKS=ROOT/'02_Notebooks/01_Data_and_Signals'
OUT=ROOT/'.admin/notebooks/picture'

def sequence_rows():
    n=json.loads((NOTEBOOKS/'01.5_Entropy.ipynb').read_text())
    text=next(''.join(c['source']) for c in n['cells'] if '#### 5.3.1 Comparing Sequences' in ''.join(c['source']))
    for line in text.splitlines():
        if not line.startswith('| ') or 'Example |' in line: continue
        label,sequence,entropy=[v.strip() for v in line.strip('|').split('|')]
        symbols=sequence.strip('`').split()
        assert len(symbols)==16
        yield label,symbols,entropy

def extended_values(symbols, index, count=4096):
    prefix=np.array([int(s,2) for s in symbols],dtype=float)
    if index <= 5:
        return np.resize(prefix,count)
    # Independent draws from the probabilities in the 16-symbol example;
    # retain those displayed symbols as the beginning of the longer record.
    rng=np.random.default_rng(1700+index)
    return np.concatenate([prefix,rng.choice(prefix,size=count-len(prefix))])

def lag_coefficients(values):
    result=[]
    for k in range(33):
        a=values[:len(values)-k] if k else values
        b=values[k:]
        if np.std(a)==0 or np.std(b)==0: result.append(np.nan)
        else: result.append(np.corrcoef(a,b)[0,1])
    return np.array(result)

if __name__=='__main__':
    for i,(label,symbols,entropy) in enumerate(sequence_rows(),1):
        values=extended_values(symbols,i)
        coefficients=lag_coefficients(values)
        fig,ax=plt.subplots(figsize=(4.5,1.85))
        ax.set_facecolor('none')
        ax.axhline(0,color='#87939c',lw=.8)
        if np.all(np.isnan(coefficients)):
            ax.text(.5,.55,'Undefined: constant sequence\n(zero standard deviation)',transform=ax.transAxes,
                    ha='center',va='center',fontsize=10)
        else:
            ax.plot(range(33),coefficients,'o-',color='#126da8',markersize=2.5,lw=1.3)
            if np.isnan(coefficients).any():
                missing=', '.join(str(k) for k in np.flatnonzero(np.isnan(coefficients)))
                ax.text(.98,.95,f'Undefined at lag {missing}\n(zero standard deviation)',transform=ax.transAxes,
                        ha='right',va='top',fontsize=8)
        ax.set(xlim=(-.5,32.5),ylim=(-1.12,1.12),xlabel='Lag k [symbols]',ylabel='Correlation')
        ax.set_xticks(range(0,33,4)); ax.set_yticks([-1,0,1]); ax.grid(alpha=.2)
        fig.tight_layout(pad=.35)
        fig.savefig(OUT/f'correlation_sequence_{i:02d}.svg',transparent=True,bbox_inches='tight',pad_inches=.03)
        plt.close(fig)
        print(f"{label}: {len(values)} symbols, lags 0-32")
