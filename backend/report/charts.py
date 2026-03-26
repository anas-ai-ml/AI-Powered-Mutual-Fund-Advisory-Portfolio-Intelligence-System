import matplotlib.pyplot as plt
import io
import base64
import numpy as np

def _fig_to_base64(fig):
    """Converts a matplotlib figure to a base64 string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', transparent=True, dpi=100)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"

def generate_risk_factor_chart(factors: dict):
    """
    factors: { "Age": 2.5, "Dependents": -1.0, ... }
    """
    labels = list(factors.keys())
    values = list(factors.values())
    
    fig, ax = plt.subplots(figsize=(6, 3))
    colors = ['#4caf50' if v >= 0 else '#f44336' for v in values]
    
    ax.barh(labels, values, color=colors)
    ax.set_xlabel('Contribution to Score')
    ax.set_title('Risk Factor Contributions')
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    
    return _fig_to_base64(fig)

def generate_sensitivity_chart(success_prob: float):
    """
    Generates a simple gauge or progress-like visualization for Monte Carlo.
    """
    fig, ax = plt.subplots(figsize=(4, 0.8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    
    # Background bar
    ax.barh([0.5], [100], color='#eee', height=0.6)
    
    # Progress bar
    color = '#4caf50' if success_prob >= 80 else ('#ff9800' if success_prob >= 50 else '#f44336')
    ax.barh([0.5], [success_prob], color=color, height=0.6)
    
    ax.text(success_prob / 2, 0.5, f"{success_prob:.0f}%", va='center', ha='center', color='white', fontweight='bold')
    
    ax.axis('off')
    return _fig_to_base64(fig)

def generate_score_gauges(scores: dict):
    """
    scores: { "Risk": 6.5, "Diversification": 9.2, ... }
    Generates 5 mini-gauges (or bars) in a single row.
    """
    fig, axes = plt.subplots(1, 5, figsize=(10, 2))
    
    for i, (name, val) in enumerate(scores.items()):
        ax = axes[i]
        scale = 10 if name != "AI Market" and name != "Market Stability" and name != "Goal Confidence" else 100
        # Normalize to 100 for color logic
        norm_val = (val / scale) * 100
        
        color = '#4caf50' if norm_val >= 80 else ('#ff9800' if norm_val >= 50 else '#f44336')
        
        ax.pie([norm_val, 100 - norm_val], colors=[color, '#eee'], startangle=90, counterclock=False, wedgeprops={'width': 0.3})
        ax.text(0, 0, f"{val:.1f}" if scale == 10 else f"{val:.0f}%", ha='center', va='center', fontweight='bold', fontsize=10)
        ax.set_title(name, fontsize=9, pad=2)
    
    plt.tight_layout()
    return _fig_to_base64(fig)
