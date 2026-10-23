"""
MiniFacts Q/K/V Inspector
=========================

Notebook-friendly utilities for inspecting Q, K, V, raw attention scores,
softmax attention weights, and sentence-level attention mass in the public
MiniFacts sentence-window models.

The public model names are:
    model_1 = left_sentence_1
    model_2 = right_sentence_1
    model_3 = both_sentence_1
    model_4 = left_sentence_2_right_sentence_1
    model_5 = left_sentence_1_right_sentence_2
    model_6 = both_sentence_2

This module does not require the Raspberry Pi to return Q/K/V tensors.  It can
load exported local checkpoints and compute inspection tensors from the model's
MultiheadAttention layers.  The optional server comparison only compares final
answers returned by the Pi.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
import json
import math
import os
import re
import urllib.request

import numpy as np
import torch
from torch import nn
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


PUBLIC_MODEL_TO_RULE: Dict[str, str] = {
    "model_1": "left_sentence_1",
    "model_2": "right_sentence_1",
    "model_3": "both_sentence_1",
    "model_4": "left_sentence_2_right_sentence_1",
    "model_5": "left_sentence_1_right_sentence_2",
    "model_6": "both_sentence_2",
}

DEFAULT_LABELS = [
    "red", "blue", "green", "yellow", "black", "white", "orange", "purple",
    "bike", "kite", "map", "bag", "book", "ball", "cup", "hat", "car", "box",
    "forest", "garden", "school", "beach", "park", "farm", "river", "cave", "house", "shop",
    "fox", "dog", "cat", "bear", "lion", "tiger", "bird", "horse", "mouse", "rabbit",
    "alice", "ben", "clara", "david", "emma", "leo", "mia", "nora", "oliver", "sophia",
    "unknown", "conflict",
]

SPECIAL_TOKENS = {"[PAD]", "<pad>", "[UNK]", "<unk>", "[CLS]", "<cls>", "[SEP]", "<sep>"}


@dataclass
class LoadedModelForInspection:
    model: nn.Module
    config: Dict[str, Any]
    vocab: Dict[str, int]
    id_to_token: Dict[int, str]
    label_list: List[str]
    device: torch.device
    model_name: str
    attention_setting: str
    model_dir: Path


@dataclass
class TokenizedPrompt:
    normalized_prompt: str
    sentence_texts: List[str]
    question_sentence_index: int
    tokens: List[str]
    token_ids: List[int]
    sentence_spans: List[List[int]]
    question_token_indices: List[int]
    special_token_indices: List[int]


@dataclass
class QKVInspectionResult:
    model_name: str
    attention_setting: str
    normalized_prompt: str
    tokens: List[str]
    token_ids: List[int]
    sentence_texts: List[str]
    sentence_spans: List[List[int]]
    question_sentence_index: int
    question_token_indices: List[int]
    visible_sentence_indices: List[int]
    hidden_states_entering_layers: List[np.ndarray]
    Q: List[np.ndarray]
    K: List[np.ndarray]
    V: List[np.ndarray]
    raw_scores: List[np.ndarray]
    masked_scores: List[np.ndarray]
    attention_weights: List[np.ndarray]
    attention_output: List[np.ndarray]
    classifier_input: Optional[np.ndarray]
    logits: Optional[np.ndarray]
    predicted_answer: str


class SimpleTokenizer:
    """Tokenizer matching the exported MiniFacts release server."""

    token_pattern = re.compile(r"[a-z]+|[0-9]+|[.?'']")

    def __init__(self, vocab: Mapping[str, int]):
        self.vocab = dict(vocab)
        self.lower_vocab = {k.lower(): v for k, v in self.vocab.items()}
        self.unk_id = self.vocab.get(
            "<UNK>", self.vocab.get("[UNK]", self.vocab.get("<unk>", 0))
        )
        self.cls_token = next(
            (
                token
                for token in ("<CLS>", "[CLS]", "<cls>")
                if token in self.vocab
            ),
            None,
        )
        self.sep_token = next(
            (
                token
                for token in ("<SEP>", "[SEP]", "<sep>")
                if token in self.vocab
            ),
            None,
        )

    def tokenize_text(self, text: str) -> List[str]:
        return self.token_pattern.findall(text.lower())

    def token_to_id(self, token: str) -> int:
        if token in self.vocab:
            return self.vocab[token]
        if token.lower() in self.lower_vocab:
            return self.lower_vocab[token.lower()]
        return self.unk_id

    def encode(self, sentence_texts: Sequence[str]) -> Tuple[List[str], List[int], List[List[int]], List[int]]:
        tokens: List[str] = []
        sentence_spans: List[List[int]] = []
        special_indices: List[int] = []

        if self.cls_token is not None:
            special_indices.append(len(tokens))
            tokens.append(self.cls_token)

        for sentence in sentence_texts:
            span: List[int] = []
            for tok in self.tokenize_text(sentence):
                span.append(len(tokens))
                tokens.append(tok)
            sentence_spans.append(span)
            if self.sep_token is not None:
                special_indices.append(len(tokens))
                tokens.append(self.sep_token)

        token_ids = [self.token_to_id(tok) for tok in tokens]
        return tokens, token_ids, sentence_spans, special_indices


def normalize_prompt(prompt: str) -> str:
    """Apply the light spelling/possessive normalization used in MiniFacts exercises."""
    text = prompt.strip()
    replacements = {
        "Alices": "Alice's",
        "Bens": "Ben's",
        "Claras": "Clara's",
        "Davids": "David's",
        "Emmas": "Emma's",
        "Leos": "Leo's",
        "Mias": "Mia's",
        "Noras": "Nora's",
        "Olivers": "Oliver's",
        "Sophias": "Sophia's",
        "colour": "color",
        "Colour": "Color",
    }
    for old, new in replacements.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_sentences(prompt: str) -> List[str]:
    """Split a MiniFacts prompt into sentence-like units while preserving punctuation."""
    parts = re.findall(r"[^.!?]+[.!?]", prompt.strip())
    parts = [p.strip() for p in parts]
    if len(parts) != 4:
        raise ValueError(f"Expected exactly four sentences, found {len(parts)}: {parts}")
    return parts


def visible_sentence_indices(question_index: int, attention_setting: str, n_sentences: int = 4) -> List[int]:
    """Return fact-sentence indices visible under the public sentence-window rule.

    The question sentence is never included as a visible fact sentence.  Invalid
    indices outside the prompt boundary are clipped away.
    """
    if attention_setting == "left_sentence_1":
        offsets = [-1]
    elif attention_setting == "right_sentence_1":
        offsets = [1]
    elif attention_setting == "both_sentence_1":
        offsets = [-1, 1]
    elif attention_setting == "left_sentence_2_right_sentence_1":
        offsets = [-2, -1, 1]
    elif attention_setting == "left_sentence_1_right_sentence_2":
        offsets = [-1, 1, 2]
    elif attention_setting == "both_sentence_2":
        offsets = [-2, -1, 1, 2]
    else:
        raise ValueError(f"Unknown attention_setting: {attention_setting}")
    return sorted(i for i in (question_index + off for off in offsets) if 0 <= i < n_sentences and i != question_index)


def _load_json_if_exists(path: Path) -> Optional[Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _find_first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


def _infer_model_name(model_dir: Path, config: Mapping[str, Any]) -> str:
    name = str(config.get("model_name") or model_dir.name)
    # normalize to public model_N naming when possible
    m = re.search(r"model_[1-6]", name)
    return m.group(0) if m else name


def _infer_attention_setting(model_name: str, config: Mapping[str, Any]) -> str:
    setting = config.get("attention_setting") or config.get("attention_rule") or config.get("window_rule")
    if setting:
        return str(setting)
    return PUBLIC_MODEL_TO_RULE.get(model_name, "both_sentence_2")


def _normalize_config(config: Mapping[str, Any], vocab_size: int, num_labels: int, model_name: str) -> Dict[str, Any]:
    cfg = dict(config)
    cfg.setdefault("vocab_size", vocab_size)
    cfg.setdefault("num_labels", num_labels)
    cfg.setdefault("max_seq_len", cfg.get("max_length", cfg.get("context_length", 128)))
    cfg.setdefault("embedding_dim", cfg.get("d_model", cfg.get("hidden_size", 96 if model_name in {"model_4", "model_6"} else 64)))
    cfg.setdefault("num_heads", cfg.get("nhead", cfg.get("n_heads", 4 if model_name in {"model_4", "model_6"} else 2)))
    cfg.setdefault("num_layers", cfg.get("n_layers", cfg.get("encoder_layers", 2)))
    cfg.setdefault("dim_feedforward", cfg.get("ff_dim", cfg.get("intermediate_size", int(cfg["embedding_dim"]) * 4)))
    cfg.setdefault("dropout", cfg.get("dropout_rate", 0.0))
    cfg.setdefault("norm_first", cfg.get("pre_norm", False))
    return cfg


class MiniFactsTransformerClassifier(nn.Module):
    """Exact architecture used by the exported MiniFacts release checkpoints."""

    def __init__(self, config: Mapping[str, Any]):
        super().__init__()
        cfg = dict(config)
        self.config = cfg
        d_model = int(cfg["embedding_dim"])
        nhead = int(cfg["num_heads"])
        dropout = float(cfg.get("dropout", 0.0))
        self.attention_heads = nhead
        self.classifier_pooling = cfg.get(
            "classifier_pooling", "question_token"
        )
        self.token_embedding = nn.Embedding(
            int(cfg["vocab_size"]),
            d_model,
            padding_idx=int(cfg.get("pad_id", 0)),
        )
        self.position_embedding = nn.Embedding(
            int(cfg.get("max_seq_len", 64)), d_model
        )
        self.attention_norm = nn.LayerNorm(d_model)
        self.attention = nn.MultiheadAttention(
            d_model,
            nhead,
            dropout=dropout,
            batch_first=True,
        )
        self.feed_forward_norm = nn.LayerNorm(d_model)
        self.feed_forward = nn.Sequential(
            nn.Linear(
                d_model,
                int(cfg.get("ff_dim", cfg.get("dim_feedforward", d_model * 2))),
            ),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(
                int(cfg.get("ff_dim", cfg.get("dim_feedforward", d_model * 2))),
                d_model,
            ),
            nn.Dropout(dropout),
        )
        self.classifier_norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, int(cfg["num_labels"]))


def _load_vocab(model_dir: Path, config: Mapping[str, Any]) -> Dict[str, int]:
    candidates = [
        model_dir / "vocab.json",
        model_dir / "vocabulary.json",
        model_dir / "token_to_id.json",
        model_dir / "tokenizer.json",
        model_dir.parent / "vocab.json",
    ]
    vocab_obj = None
    for path in candidates:
        vocab_obj = _load_json_if_exists(path)
        if vocab_obj is not None:
            break
    if isinstance(vocab_obj, dict):
        # HuggingFace tokenizers often nest the vocab under model.vocab.
        if "model" in vocab_obj and isinstance(vocab_obj["model"], dict) and "vocab" in vocab_obj["model"]:
            vocab_obj = vocab_obj["model"]["vocab"]
        if all(isinstance(v, int) for v in vocab_obj.values()):
            return {str(k): int(v) for k, v in vocab_obj.items()}
        if "vocab" in vocab_obj and isinstance(vocab_obj["vocab"], dict):
            return {str(k): int(v) for k, v in vocab_obj["vocab"].items()}
    # Fallback MiniFacts vocabulary, enough for notebook diagnostics and synthetic tests.
    base = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", ".", "?", "'s", "has", "a", "an", "the", "What", "what", "color", "does", "Where", "where", "Which", "which", "Who", "who", "is", "carries", "carry", "sleeps", "sleep", "likes", "like", "in"]
    names = ["Alice", "Ben", "Clara", "David", "Emma", "Leo", "Mia", "Nora", "Oliver", "Sophia"]
    colors = ["red", "blue", "green", "yellow", "black", "white", "orange", "purple"]
    objects = ["bike", "kite", "map", "bag", "book", "ball", "cup", "hat", "car", "box"]
    animals = ["fox", "dog", "cat", "bear", "lion", "tiger", "bird", "horse", "mouse", "rabbit"]
    places = ["forest", "garden", "school", "beach", "park", "farm", "river", "cave", "house", "shop"]
    vocab_tokens = []
    for tok in base + names + [n.lower() for n in names] + colors + objects + animals + places:
        if tok not in vocab_tokens:
            vocab_tokens.append(tok)
    return {tok: i for i, tok in enumerate(vocab_tokens)}


def _load_labels(model_dir: Path, config: Mapping[str, Any]) -> List[str]:
    for fname in [
        "label_vocab.json",
        "labels.json",
        "label_list.json",
        "classes.json",
        "id_to_label.json",
        "label_encoder.json",
    ]:
        obj = _load_json_if_exists(model_dir / fname)
        if obj is None:
            continue
        if isinstance(obj, list):
            return [str(x) for x in obj]
        if isinstance(obj, dict):
            if "labels" in obj and isinstance(obj["labels"], list):
                return [str(x) for x in obj["labels"]]
            if "classes" in obj and isinstance(obj["classes"], list):
                return [str(x) for x in obj["classes"]]
            if all(
                isinstance(label, str) and isinstance(index, int)
                for label, index in obj.items()
            ):
                return [
                    label
                    for label, _ in sorted(
                        obj.items(), key=lambda item: item[1]
                    )
                ]
            if all(str(k).isdigit() for k in obj.keys()):
                return [str(obj[str(i)] if str(i) in obj else obj[i]) for i in range(len(obj))]
    n = int(config.get("num_labels", config.get("num_classes", len(DEFAULT_LABELS)))) if config else len(DEFAULT_LABELS)
    if n <= len(DEFAULT_LABELS):
        return DEFAULT_LABELS[:n]
    return DEFAULT_LABELS + [f"label_{i}" for i in range(len(DEFAULT_LABELS), n)]


def _extract_state_dict(checkpoint: Any) -> Mapping[str, torch.Tensor]:
    if isinstance(checkpoint, Mapping):
        for key in ["model_state_dict", "state_dict", "model", "net"]:
            if key in checkpoint and isinstance(checkpoint[key], Mapping):
                return checkpoint[key]
        if all(isinstance(v, torch.Tensor) for v in checkpoint.values()):
            return checkpoint  # raw state dict
    raise ValueError("Checkpoint does not contain a recognizable model state dict.")


def load_model_for_inspection(
    model_dir: str,
    checkpoint_name: str = "best_combined_checkpoint.pt",
    device: str = "cpu",
) -> LoadedModelForInspection:
    """Load an exported MiniFacts checkpoint for local Q/K/V inspection.

    The function supports both `release_models/model_N` and
    `exports_sentence_release6/attention_server/release_models/model_N` layouts.
    """
    model_path = Path(model_dir)
    if not model_path.exists():
        alternatives = [Path("exports_sentence_release6/attention_server") / model_path, Path.cwd() / model_path]
        alt = _find_first_existing(alternatives)
        if alt is not None:
            model_path = alt
        else:
            raise FileNotFoundError(
                f"Could not find model_dir={model_dir!r}. Place exported checkpoints under release_models/model_1 ... model_6."
            )
    config = _load_json_if_exists(model_path / "config.json") or {}
    model_name = _infer_model_name(model_path, config)
    attention_setting = _infer_attention_setting(model_name, config)
    vocab = _load_vocab(model_path, config)
    id_to_token = {v: k for k, v in vocab.items()}
    labels = _load_labels(model_path, config)
    norm_config = _normalize_config(config, vocab_size=len(vocab), num_labels=len(labels), model_name=model_name)
    norm_config["num_labels"] = int(norm_config.get("num_labels", len(labels)))
    norm_config["pad_id"] = int(vocab.get("<PAD>", vocab.get("[PAD]", 0)))

    model = MiniFactsTransformerClassifier(norm_config)
    ckpt_path = model_path / checkpoint_name
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Could not find checkpoint: {ckpt_path}")
    checkpoint = torch.load(ckpt_path, map_location=device)
    state_dict = _extract_state_dict(checkpoint)
    model.load_state_dict(state_dict, strict=True)

    dev = torch.device(device)
    model.to(dev)
    model.eval()
    return LoadedModelForInspection(
        model=model,
        config=norm_config,
        vocab=vocab,
        id_to_token=id_to_token,
        label_list=labels,
        device=dev,
        model_name=model_name,
        attention_setting=attention_setting,
        model_dir=model_path,
    )


def tokenize_with_sentence_spans(prompt: str, loaded_model: LoadedModelForInspection) -> TokenizedPrompt:
    normalized = normalize_prompt(prompt)
    sentences = split_sentences(normalized)
    question_indices = [i for i, s in enumerate(sentences) if s.strip().endswith("?")]
    if len(question_indices) != 1:
        raise ValueError(f"Expected exactly one question sentence ending in '?', found {len(question_indices)}.")
    tokenizer = SimpleTokenizer(loaded_model.vocab)
    tokens, token_ids, sentence_spans, special_indices = tokenizer.encode(sentences)
    q_idx = question_indices[0]
    question_token_indices = sentence_spans[q_idx]
    return TokenizedPrompt(
        normalized_prompt=normalized,
        sentence_texts=sentences,
        question_sentence_index=q_idx,
        tokens=tokens,
        token_ids=token_ids,
        sentence_spans=sentence_spans,
        question_token_indices=question_token_indices,
        special_token_indices=special_indices,
    )


def _get_encoder_layers(model: nn.Module) -> List[nn.TransformerEncoderLayer]:
    if hasattr(model, "encoder_layers"):
        return list(getattr(model, "encoder_layers"))
    for attr in ["encoder", "transformer_encoder", "layers"]:
        obj = getattr(model, attr, None)
        if obj is None:
            continue
        if hasattr(obj, "layers"):
            return list(obj.layers)
        if isinstance(obj, nn.ModuleList):
            return list(obj)
    layers = [m for m in model.modules() if isinstance(m, nn.TransformerEncoderLayer)]
    if layers:
        return layers
    raise TypeError("Could not locate TransformerEncoderLayer blocks in model.")


def _get_embeddings(model: nn.Module) -> Tuple[nn.Module, Optional[nn.Module]]:
    token_emb = None
    for attr in ["token_embedding", "embedding", "embeddings", "embed", "word_embeddings"]:
        obj = getattr(model, attr, None)
        if isinstance(obj, nn.Embedding):
            token_emb = obj
            break
    if token_emb is None:
        # search first embedding
        embeddings = [m for m in model.modules() if isinstance(m, nn.Embedding)]
        if not embeddings:
            raise TypeError("Could not find token embedding in model.")
        token_emb = embeddings[0]
    pos_emb = None
    for attr in ["position_embedding", "pos_embedding", "position_embeddings", "positional_embedding"]:
        obj = getattr(model, attr, None)
        if isinstance(obj, nn.Embedding):
            pos_emb = obj
            break
    return token_emb, pos_emb


def _get_classifier(model: nn.Module) -> Optional[nn.Module]:
    for attr in ["classifier", "classification_head", "head", "fc", "output", "linear"]:
        obj = getattr(model, attr, None)
        if isinstance(obj, nn.Module):
            return obj
    return None


def _sentence_key_mask(tokenized: TokenizedPrompt, setting: str) -> torch.Tensor:
    n = len(tokenized.tokens)
    q_idx = tokenized.question_sentence_index
    vis_sent = visible_sentence_indices(q_idx, setting, len(tokenized.sentence_texts))
    # This exactly mirrors the release model: the question sentence and
    # permitted fact sentences are visible; <CLS> is not automatically added.
    allowed = set(tokenized.sentence_spans[q_idx])
    for si in vis_sent:
        allowed.update(tokenized.sentence_spans[si])
    visible = torch.zeros(n, dtype=torch.bool)
    for i in allowed:
        if 0 <= i < n:
            visible[i] = True
    # additive attention mask: same visible key columns for every query row
    mask = torch.zeros(n, n, dtype=torch.float32)
    mask[:, ~visible] = float("-inf")
    return mask


def _reshape_qkv(x: torch.Tensor, num_heads: int) -> torch.Tensor:
    # x: [1, seq_len, embed_dim] -> [num_heads, seq_len, head_dim]
    batch, seq_len, embed_dim = x.shape
    head_dim = embed_dim // num_heads
    return x.view(batch, seq_len, num_heads, head_dim).transpose(1, 2).squeeze(0).contiguous()


def _feed_forward(layer: nn.TransformerEncoderLayer, x: torch.Tensor) -> torch.Tensor:
    x2 = layer.linear2(layer.dropout(layer.activation(layer.linear1(x))))
    return layer.dropout2(x2)


def _manual_transformer_layer(
    layer: nn.TransformerEncoderLayer,
    x: torch.Tensor,
    additive_attn_mask: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
    """Run one encoder layer while extracting Q/K/V and attention weights."""
    mha = layer.self_attn
    num_heads = int(mha.num_heads)
    embed_dim = int(mha.embed_dim)
    head_dim = embed_dim // num_heads
    norm_first = bool(getattr(layer, "norm_first", False))
    x_for_qkv = layer.norm1(x) if norm_first else x

    W = mha.in_proj_weight
    b = mha.in_proj_bias
    if W is None:
        raise TypeError("Expected combined in_proj_weight in MultiheadAttention.")
    W_Q, W_K, W_V = W[0:embed_dim, :], W[embed_dim:2*embed_dim, :], W[2*embed_dim:3*embed_dim, :]
    if b is None:
        b_Q = b_K = b_V = torch.zeros(embed_dim, device=x.device, dtype=x.dtype)
    else:
        b_Q, b_K, b_V = b[0:embed_dim], b[embed_dim:2*embed_dim], b[2*embed_dim:3*embed_dim]

    Q_full = x_for_qkv @ W_Q.T + b_Q
    K_full = x_for_qkv @ W_K.T + b_K
    V_full = x_for_qkv @ W_V.T + b_V
    Q = _reshape_qkv(Q_full, num_heads)
    K = _reshape_qkv(K_full, num_heads)
    V = _reshape_qkv(V_full, num_heads)

    raw_scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(head_dim)
    if additive_attn_mask is not None:
        mask = additive_attn_mask.to(device=x.device, dtype=raw_scores.dtype)
        masked_scores = raw_scores + mask.unsqueeze(0)
    else:
        masked_scores = raw_scores
    attention_weights = torch.softmax(masked_scores, dim=-1)
    attention_output_heads = torch.matmul(attention_weights, V)

    # Run the actual layer operations using PyTorch's MultiheadAttention so the
    # next layer receives the same style of hidden state as normal inference.
    attn_mask = additive_attn_mask.to(device=x.device, dtype=x.dtype) if additive_attn_mask is not None else None
    attn_output, _ = mha(
        x_for_qkv,
        x_for_qkv,
        x_for_qkv,
        attn_mask=attn_mask,
        need_weights=False,
    )
    if norm_first:
        x = x + layer.dropout1(attn_output)
        x = x + _feed_forward(layer, layer.norm2(x))
    else:
        x = layer.norm1(x + layer.dropout1(attn_output))
        x = layer.norm2(x + _feed_forward(layer, x))

    tensors = {
        "hidden_for_qkv": x_for_qkv,
        "Q": Q,
        "K": K,
        "V": V,
        "raw_scores": raw_scores,
        "masked_scores": masked_scores,
        "attention_weights": attention_weights,
        "attention_output": attention_output_heads,
    }
    return x, tensors


def _manual_minifacts_block(
    model: MiniFactsTransformerClassifier,
    x: torch.Tensor,
    additive_attn_mask: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
    """Run the release model's single attention block and expose Q/K/V."""
    mha = model.attention
    num_heads = int(mha.num_heads)
    embed_dim = int(mha.embed_dim)
    head_dim = embed_dim // num_heads
    normalized = model.attention_norm(x)

    weight = mha.in_proj_weight
    bias = mha.in_proj_bias
    if weight is None:
        raise TypeError("Expected combined in_proj_weight in MultiheadAttention.")
    W_Q, W_K, W_V = weight.chunk(3, dim=0)
    if bias is None:
        b_Q = b_K = b_V = torch.zeros(
            embed_dim, device=x.device, dtype=x.dtype
        )
    else:
        b_Q, b_K, b_V = bias.chunk(3, dim=0)

    Q = _reshape_qkv(normalized @ W_Q.T + b_Q, num_heads)
    K = _reshape_qkv(normalized @ W_K.T + b_K, num_heads)
    V = _reshape_qkv(normalized @ W_V.T + b_V, num_heads)
    raw_scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(
        head_dim
    )
    if additive_attn_mask is None:
        masked_scores = raw_scores
        attention_mask = None
    else:
        attention_mask = additive_attn_mask.to(
            device=x.device, dtype=raw_scores.dtype
        )
        masked_scores = raw_scores + attention_mask.unsqueeze(0)
    attention_weights = torch.softmax(masked_scores, dim=-1)
    attention_output_heads = torch.matmul(attention_weights, V)

    attended, _ = mha(
        normalized,
        normalized,
        normalized,
        attn_mask=attention_mask,
        need_weights=False,
    )
    hidden = x + attended
    hidden = hidden + model.feed_forward(
        model.feed_forward_norm(hidden)
    )
    return hidden, {
        "hidden_for_qkv": normalized,
        "Q": Q,
        "K": K,
        "V": V,
        "raw_scores": raw_scores,
        "masked_scores": masked_scores,
        "attention_weights": attention_weights,
        "attention_output": attention_output_heads,
    }


def extract_qkv_for_prompt(
    loaded_model: LoadedModelForInspection,
    prompt: str,
) -> QKVInspectionResult:
    """Compute Q/K/V, raw scores, masked scores, attention weights, and logits."""
    model = loaded_model.model
    model.eval()
    tokenized = tokenize_with_sentence_spans(prompt, loaded_model)
    token_ids = torch.tensor([tokenized.token_ids], dtype=torch.long, device=loaded_model.device)
    token_emb, pos_emb = _get_embeddings(model)
    classifier = _get_classifier(model)

    with torch.no_grad():
        x = token_emb(token_ids)
        if pos_emb is not None:
            seq_len = token_ids.shape[1]
            positions = torch.arange(seq_len, device=loaded_model.device).unsqueeze(0)
            max_pos = getattr(pos_emb, "num_embeddings", seq_len)
            if seq_len > max_pos:
                raise ValueError(f"Prompt has {seq_len} tokens, but position embedding supports {max_pos}.")
            x = x + pos_emb(positions)
        additive_mask = _sentence_key_mask(tokenized, loaded_model.attention_setting).to(loaded_model.device)

        hidden_states_entering_layers: List[np.ndarray] = []
        Qs: List[np.ndarray] = []
        Ks: List[np.ndarray] = []
        Vs: List[np.ndarray] = []
        raw_scores: List[np.ndarray] = []
        masked_scores: List[np.ndarray] = []
        attention_weights: List[np.ndarray] = []
        attention_outputs: List[np.ndarray] = []

        if isinstance(model, MiniFactsTransformerClassifier):
            blocks = [model]
        else:
            blocks = _get_encoder_layers(model)

        for block in blocks:
            if isinstance(block, MiniFactsTransformerClassifier):
                x, tensors = _manual_minifacts_block(
                    block, x, additive_mask
                )
            else:
                x, tensors = _manual_transformer_layer(
                    block, x, additive_mask
                )
            hidden_states_entering_layers.append(tensors["hidden_for_qkv"].squeeze(0).detach().cpu().numpy())
            Qs.append(tensors["Q"].detach().cpu().numpy())
            Ks.append(tensors["K"].detach().cpu().numpy())
            Vs.append(tensors["V"].detach().cpu().numpy())
            raw_scores.append(tensors["raw_scores"].detach().cpu().numpy())
            masked_scores.append(tensors["masked_scores"].detach().cpu().numpy())
            attention_weights.append(tensors["attention_weights"].detach().cpu().numpy())
            attention_outputs.append(tensors["attention_output"].detach().cpu().numpy())

        classifier_input_arr: Optional[np.ndarray]
        logits_arr: Optional[np.ndarray]
        predicted = "unavailable"
        if classifier is not None:
            q_idx = torch.tensor(tokenized.question_token_indices, dtype=torch.long, device=loaded_model.device)
            pooled = x[:, q_idx, :].mean(dim=1) if len(q_idx) else x.mean(dim=1)
            classifier_norm = getattr(model, "classifier_norm", None)
            if isinstance(classifier_norm, nn.Module):
                pooled = classifier_norm(pooled)
            classifier_input_arr = (
                pooled.detach().cpu().numpy().squeeze(0)
            )
            logits = classifier(pooled)
            logits_arr = logits.detach().cpu().numpy().squeeze(0)
            pred_id = int(logits.argmax(dim=-1).item())
            predicted = loaded_model.label_list[pred_id] if pred_id < len(loaded_model.label_list) else str(pred_id)
        else:
            classifier_input_arr = None
            logits_arr = None

    return QKVInspectionResult(
        model_name=loaded_model.model_name,
        attention_setting=loaded_model.attention_setting,
        normalized_prompt=tokenized.normalized_prompt,
        tokens=tokenized.tokens,
        token_ids=tokenized.token_ids,
        sentence_texts=tokenized.sentence_texts,
        sentence_spans=tokenized.sentence_spans,
        question_sentence_index=tokenized.question_sentence_index,
        question_token_indices=tokenized.question_token_indices,
        visible_sentence_indices=visible_sentence_indices(tokenized.question_sentence_index, loaded_model.attention_setting, len(tokenized.sentence_texts)),
        hidden_states_entering_layers=hidden_states_entering_layers,
        Q=Qs,
        K=Ks,
        V=Vs,
        raw_scores=raw_scores,
        masked_scores=masked_scores,
        attention_weights=attention_weights,
        attention_output=attention_outputs,
        classifier_input=classifier_input_arr,
        logits=logits_arr,
        predicted_answer=predicted,
    )


def _indices_for_query_tokens(inspection: QKVInspectionResult, query_tokens: Union[str, Sequence[int]]) -> List[int]:
    if query_tokens == "question":
        return list(inspection.question_token_indices)
    if query_tokens == "all":
        return list(range(len(inspection.tokens)))
    return [int(i) for i in query_tokens]


def _resolve_layer(inspection: QKVInspectionResult, layer: Union[int, str]) -> int:
    if layer == "last":
        return len(inspection.attention_weights) - 1
    return int(layer)


def _resolve_attention_matrix(inspection: QKVInspectionResult, layer: Union[int, str], head: Union[int, str], which: str = "weights") -> np.ndarray:
    layer_idx = _resolve_layer(inspection, layer)
    arr = getattr(inspection, which)[layer_idx]
    if head == "mean":
        return arr.mean(axis=0)
    return arr[int(head)]


def _add_sentence_boundaries(ax: plt.Axes, inspection: QKVInspectionResult, row_offset: float = -0.5) -> None:
    for span in inspection.sentence_spans:
        if not span:
            continue
        start, end = min(span), max(span) + 1
        ax.axvline(start - 0.5, linewidth=0.8)
        ax.axvline(end - 0.5, linewidth=0.8)


def plot_sentence_window_rule(prompt: str, attention_setting: str):
    """Visualize the public sentence-window rule as sentence blocks."""
    sentences = split_sentences(normalize_prompt(prompt))
    q_idx = next(i for i, s in enumerate(sentences) if s.endswith("?"))
    visible = set(visible_sentence_indices(q_idx, attention_setting, len(sentences)))
    fig, ax = plt.subplots(figsize=(10, 2.5))
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for i, sentence in enumerate(sentences):
        if i == q_idx:
            alpha = 1.0
            hatch = "//"
            label = "question"
        elif i in visible:
            alpha = 0.95
            hatch = None
            label = "visible fact"
        else:
            alpha = 0.25
            hatch = None
            label = "masked fact"
        rect = Rectangle((i + 0.04, 0.18), 0.92, 0.60, alpha=alpha, hatch=hatch, fill=True)
        ax.add_patch(rect)
        ax.text(i + 0.5, 0.70, f"S{i}: {label}", ha="center", va="center", fontsize=10, fontweight="bold")
        ax.text(i + 0.5, 0.45, sentence, ha="center", va="center", fontsize=9, wrap=True)
    ax.set_title(f"Public sentence-window rule: {attention_setting}")
    plt.tight_layout()
    return fig, ax


def plot_token_attention(
    inspection: QKVInspectionResult,
    layer: Union[int, str] = 0,
    head: Union[int, str] = 0,
    query_tokens: Union[str, Sequence[int]] = "question",
):
    mat = _resolve_attention_matrix(inspection, layer, head, which="attention_weights")
    rows = _indices_for_query_tokens(inspection, query_tokens)
    data = mat[rows, :]
    fig, ax = plt.subplots(figsize=(max(8, len(inspection.tokens) * 0.45), max(2.6, len(rows) * 0.45)))
    im = ax.imshow(data, aspect="auto", vmin=0, vmax=max(1e-9, data.max()))
    ax.set_xticks(range(len(inspection.tokens)))
    ax.set_xticklabels(inspection.tokens, rotation=65, ha="right")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([inspection.tokens[i] for i in rows])
    ax.set_xlabel("key/value token receiving attention")
    ax.set_ylabel("query token")
    _add_sentence_boundaries(ax, inspection)
    title_head = "mean head" if head == "mean" else f"head {head}"
    ax.set_title(f"{inspection.model_name} | {inspection.attention_setting} | layer {layer}, {title_head}: softmax attention")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    plt.tight_layout()
    return fig, ax


def plot_qk_scores(
    inspection: QKVInspectionResult,
    layer: Union[int, str] = 0,
    head: Union[int, str] = 0,
    query_tokens: Union[str, Sequence[int]] = "question",
):
    mat = _resolve_attention_matrix(inspection, layer, head, which="raw_scores")
    rows = _indices_for_query_tokens(inspection, query_tokens)
    data = mat[rows, :]
    fig, ax = plt.subplots(figsize=(max(8, len(inspection.tokens) * 0.45), max(2.6, len(rows) * 0.45)))
    im = ax.imshow(data, aspect="auto")
    ax.set_xticks(range(len(inspection.tokens)))
    ax.set_xticklabels(inspection.tokens, rotation=65, ha="right")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([inspection.tokens[i] for i in rows])
    ax.set_xlabel("key token")
    ax.set_ylabel("query token")
    _add_sentence_boundaries(ax, inspection)
    title_head = "mean head" if head == "mean" else f"head {head}"
    ax.set_title(f"{inspection.model_name} | {inspection.attention_setting} | layer {layer}, {title_head}: raw QK/√d scores")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    plt.tight_layout()
    return fig, ax


def sentence_attention_mass(
    inspection: QKVInspectionResult,
    layer: Union[int, str] = "last",
    head: Union[int, str] = "mean",
) -> np.ndarray:
    mat = _resolve_attention_matrix(inspection, layer, head, which="attention_weights")
    rows = np.array(inspection.question_token_indices, dtype=int)
    if len(rows) == 0:
        return np.zeros(len(inspection.sentence_spans))
    question_to_all = mat[rows, :].mean(axis=0)
    masses = []
    for span in inspection.sentence_spans:
        masses.append(float(question_to_all[span].sum()) if span else 0.0)
    total = sum(masses)
    if total > 0:
        masses = [m / total for m in masses]
    return np.array(masses)


def plot_sentence_attention_mass(
    inspection: QKVInspectionResult,
    layer: Union[int, str] = "last",
    head: Union[int, str] = "mean",
):
    masses = sentence_attention_mass(inspection, layer=layer, head=head)
    labels = [f"S{i}" for i in range(len(masses))]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    bars = ax.bar(labels, masses)
    ax.set_ylim(0, max(1.0, masses.max() * 1.2 if len(masses) else 1.0))
    ax.set_ylabel("attention mass from question tokens")
    ax.set_title(f"Sentence-level neural attention mass: {inspection.model_name} | {inspection.attention_setting}")
    visible = set(inspection.visible_sentence_indices)
    for i, bar in enumerate(bars):
        marker = "question" if i == inspection.question_sentence_index else ("visible by rule" if i in visible else "masked by rule")
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02, marker, ha="center", va="bottom", fontsize=8, rotation=20)
    plt.tight_layout()
    return fig, ax


def plot_qkv_norms(
    inspection: QKVInspectionResult,
    layer: Union[int, str] = 0,
    head: Union[int, str] = "mean",
):
    layer_idx = _resolve_layer(inspection, layer)
    if head == "mean":
        Q = np.linalg.norm(inspection.Q[layer_idx], axis=-1).mean(axis=0)
        K = np.linalg.norm(inspection.K[layer_idx], axis=-1).mean(axis=0)
        V = np.linalg.norm(inspection.V[layer_idx], axis=-1).mean(axis=0)
    else:
        h = int(head)
        Q = np.linalg.norm(inspection.Q[layer_idx][h], axis=-1)
        K = np.linalg.norm(inspection.K[layer_idx][h], axis=-1)
        V = np.linalg.norm(inspection.V[layer_idx][h], axis=-1)
    x = np.arange(len(inspection.tokens))
    fig, ax = plt.subplots(figsize=(max(9, len(inspection.tokens) * 0.45), 3.4))
    ax.plot(x, Q, marker="o", label="||Q||")
    ax.plot(x, K, marker="o", label="||K||")
    ax.plot(x, V, marker="o", label="||V||")
    ax.set_xticks(x)
    ax.set_xticklabels(inspection.tokens, rotation=65, ha="right")
    ax.set_ylabel("vector norm")
    ax.set_title(f"Q/K/V vector sizes by token: {inspection.model_name} | layer {layer}")
    _add_sentence_boundaries(ax, inspection)
    ax.legend()
    plt.tight_layout()
    return fig, ax


def compare_models_sentence_attention(
    prompt: str,
    model_dirs: Mapping[str, str],
    layer: Union[int, str] = "last",
    head: Union[int, str] = "mean",
) -> pd.DataFrame:
    import pandas as pd

    rows: List[Dict[str, Any]] = []
    heat_values: List[np.ndarray] = []
    row_labels: List[str] = []
    visible_annotations: List[List[str]] = []
    for public_name, model_dir in model_dirs.items():
        loaded = load_model_for_inspection(model_dir)
        inspection = extract_qkv_for_prompt(loaded, prompt)
        masses = sentence_attention_mass(inspection, layer=layer, head=head)
        heat_values.append(masses)
        row_labels.append(public_name)
        visible_set = set(inspection.visible_sentence_indices)
        visible_annotations.append(["✓" if i in visible_set else ("Q" if i == inspection.question_sentence_index else "") for i in range(len(masses))])
        row = {
            "model": public_name,
            "attention_setting": inspection.attention_setting,
            "predicted_answer": inspection.predicted_answer,
            "visible_by_rule": ", ".join(f"S{i}" for i in inspection.visible_sentence_indices),
        }
        for i, m in enumerate(masses):
            row[f"S{i}_attention_mass"] = float(m)
        rows.append(row)
    df = pd.DataFrame(rows)

    if heat_values:
        heat = np.vstack(heat_values)
        fig, ax = plt.subplots(figsize=(7, max(3, 0.45 * len(row_labels))))
        im = ax.imshow(heat, aspect="auto", vmin=0, vmax=max(1e-9, heat.max()))
        ax.set_xticks(range(heat.shape[1]))
        ax.set_xticklabels([f"S{i}" for i in range(heat.shape[1])])
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels)
        ax.set_title("Neural attention mass from question tokens by public model")
        for i in range(heat.shape[0]):
            for j in range(heat.shape[1]):
                text = f"{heat[i, j]:.2f}{visible_annotations[i][j]}"
                ax.text(j, i, text, ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        plt.tight_layout()
        plt.show()
    return df


def _post_json(url: str, payload: Mapping[str, Any], timeout: int = 6) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_compare_result(result: Any) -> Dict[str, str]:
    if isinstance(result, dict):
        if "responses" in result and isinstance(result["responses"], list):
            return {str(r.get("model") or r.get("name") or r.get("id")): str(r.get("answer") or r.get("response") or r.get("prediction") or r.get("label")) for r in result["responses"] if isinstance(r, dict)}
        if "results" in result and isinstance(result["results"], list):
            return {str(r.get("model") or r.get("name") or r.get("id")): str(r.get("answer") or r.get("response") or r.get("prediction") or r.get("label")) for r in result["results"] if isinstance(r, dict)}
        return {k: str(v) for k, v in result.items() if str(k).startswith("model_")}
    return {}


def compare_local_inspection_to_server(
    prompt: str,
    server_url: str = "http://172.31.250.1:8000",
    model_dirs: Optional[Mapping[str, str]] = None,
) -> pd.DataFrame:
    """Compare local checkpoint answers with Pi /compare answers.

    This function does not fetch Q/K/V tensors from the Pi.  It uses the Pi only
    for normal final-answer inference.
    """
    import pandas as pd

    if model_dirs is None:
        model_dirs = {f"model_{i}": f"release_models/model_{i}" for i in range(1, 7)}
    server_result = _post_json(server_url.rstrip("/") + "/compare", {"prompt": prompt})
    server_answers = _parse_compare_result(server_result)
    rows = []
    for public_name, model_dir in model_dirs.items():
        loaded = load_model_for_inspection(model_dir)
        inspection = extract_qkv_for_prompt(loaded, prompt)
        masses = sentence_attention_mass(inspection)
        row = {
            "model": public_name,
            "attention_setting": inspection.attention_setting,
            "local_predicted_answer": inspection.predicted_answer,
            "server_answer": server_answers.get(public_name, "missing"),
            "matches_server": inspection.predicted_answer == server_answers.get(public_name, "missing"),
        }
        for i, m in enumerate(masses):
            row[f"S{i}_attention_mass"] = float(m)
        rows.append(row)
    return pd.DataFrame(rows)


# Optional client if a course server exposes small precomputed attention summaries.
# Not used by the inspector and not required for Q/K/V extraction.
def fetch_server_attention_summary(
    prompt: str,
    model: str = "model_4",
    server_url: str = "http://172.31.250.1:8000",
    endpoint: str = "/attention_weights",
) -> Any:
    """Fetch a small server-side attention summary if your Pi exposes one.

    This is optional.  The local inspector computes Q/K/V from checkpoints and
    does not depend on this endpoint.
    """
    return _post_json(server_url.rstrip("/") + endpoint, {"prompt": prompt, "model": model})


def save_inspection_bundle(
    model_dir: str,
    prompt: str,
    output_dir: str,
) -> Dict[str, Any]:
    """Save notebook-friendly tensors from one real checkpoint."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    loaded = load_model_for_inspection(model_dir)
    inspection = extract_qkv_for_prompt(loaded, prompt)
    classifier = _get_classifier(loaded.model)
    if not isinstance(classifier, nn.Linear):
        raise TypeError(
            "Expected a linear classifier for numerical inspection."
        )
    data_filename = "inspection_arrays.npz"
    np.savez(
        destination / data_filename,
        Q=inspection.Q[0],
        K=inspection.K[0],
        V=inspection.V[0],
        raw_scores=inspection.raw_scores[0],
        masked_scores=inspection.masked_scores[0],
        attention_weights=inspection.attention_weights[0],
        classifier_input=(
            inspection.classifier_input
            if inspection.classifier_input is not None
            else np.array([], dtype=np.float32)
        ),
        logits=(
            inspection.logits
            if inspection.logits is not None
            else np.array([], dtype=np.float32)
        ),
        classifier_weight=classifier.weight.detach().cpu().numpy(),
        classifier_bias=(
            classifier.bias.detach().cpu().numpy()
            if classifier.bias is not None
            else np.zeros(classifier.out_features, dtype=np.float32)
        ),
        sentence_attention_mass=sentence_attention_mass(
            inspection, layer=0, head="mean"
        ),
    )
    summary = {
        "model": inspection.model_name,
        "attention_setting": inspection.attention_setting,
        "prediction": inspection.predicted_answer,
        "tokens": inspection.tokens,
        "sentence_texts": inspection.sentence_texts,
        "sentence_spans": inspection.sentence_spans,
        "question_sentence_index": inspection.question_sentence_index,
        "question_token_indices": inspection.question_token_indices,
        "visible_sentence_indices": inspection.visible_sentence_indices,
        "labels": loaded.label_list,
        "q_shape": list(inspection.Q[0].shape),
        "k_shape": list(inspection.K[0].shape),
        "v_shape": list(inspection.V[0].shape),
        "data_file": data_filename,
    }
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect one exported MiniFacts checkpoint."
    )
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    summary = save_inspection_bundle(
        args.model_dir, args.prompt, args.output_dir
    )
    print(json.dumps(summary, indent=2))
    return 0


__all__ = [
    "PUBLIC_MODEL_TO_RULE",
    "LoadedModelForInspection",
    "TokenizedPrompt",
    "QKVInspectionResult",
    "load_model_for_inspection",
    "tokenize_with_sentence_spans",
    "visible_sentence_indices",
    "extract_qkv_for_prompt",
    "plot_sentence_window_rule",
    "plot_token_attention",
    "plot_qk_scores",
    "plot_sentence_attention_mass",
    "plot_qkv_norms",
    "compare_models_sentence_attention",
    "compare_local_inspection_to_server",
    "fetch_server_attention_summary",
    "sentence_attention_mass",
    "save_inspection_bundle",
]


if __name__ == "__main__":
    raise SystemExit(_main())
