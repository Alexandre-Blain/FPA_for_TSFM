from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import torch


DEFAULT_CHRONOS_MODEL_ID = "amazon/chronos-t5-mini"


@dataclass
class ChronosConfigLite:
    """Minimal Chronos v1 config needed for raw Transformers inference.

    This intentionally mirrors the Chronos v1 Hugging Face config fields without
    depending on the `chronos-forecasting` package. It is designed for original
    Chronos-T5 models, not Chronos-Bolt.
    """

    tokenizer_class: str
    tokenizer_kwargs: Dict[str, Any]
    context_length: int
    prediction_length: int
    n_tokens: int
    n_special_tokens: int
    pad_token_id: int
    eos_token_id: int
    use_eos_token: bool
    model_type: str
    num_samples: int = 20
    temperature: float = 1.0
    top_k: int = 50
    top_p: float = 1.0

    @classmethod
    def from_transformers_config(cls, hf_config: Any) -> "ChronosConfigLite":
        if not hasattr(hf_config, "chronos_config"):
            raise ValueError(
                "This Hugging Face config has no `chronos_config`. "
                "Use an original Chronos v1 model such as amazon/chronos-t5-mini."
            )
        return cls(**dict(hf_config.chronos_config))


class MeanScaleUniformBinsLite:
    """Chronos v1 mean-scale uniform-bin tokenizer.

    This is a compact reimplementation of the tokenizer behavior used by
    original Chronos v1 T5 checkpoints. The important point for FPA is that
    continuous values become discrete token-bin IDs, and token IDs can be forced
    during autoregressive decoding.
    """

    def __init__(self, low_limit: float, high_limit: float, config: ChronosConfigLite) -> None:
        self.config = config
        self.centers = torch.linspace(
            float(low_limit),
            float(high_limit),
            int(config.n_tokens - config.n_special_tokens - 1),
        )
        self.boundaries = torch.cat(
            (
                torch.tensor([-1e20]),
                (self.centers[1:] + self.centers[:-1]) / 2,
                torch.tensor([1e20]),
            )
        )

    def _input_transform(
        self,
        context: torch.Tensor,
        scale: torch.Tensor | None = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        context = context.to(dtype=torch.float32)
        attention_mask = ~torch.isnan(context)

        if scale is None:
            denom = torch.nansum(attention_mask, dim=-1).clamp_min(1)
            scale = torch.nansum(torch.abs(context) * attention_mask, dim=-1) / denom
            scale[~(scale > 0)] = 1.0

        boundaries = self.boundaries.to(device=context.device)
        scaled_context = context / scale.unsqueeze(dim=-1)
        token_ids = torch.bucketize(scaled_context, boundaries, right=True) + self.config.n_special_tokens
        token_ids.clamp_(0, self.config.n_tokens - 1)
        token_ids[~attention_mask] = self.config.pad_token_id
        return token_ids.long(), attention_mask.bool(), scale

    def _append_eos_token(
        self,
        token_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        eos_tokens = torch.full(
            (token_ids.shape[0], 1),
            fill_value=self.config.eos_token_id,
            device=token_ids.device,
            dtype=token_ids.dtype,
        )
        eos_mask = torch.ones((attention_mask.shape[0], 1), device=attention_mask.device, dtype=torch.bool)
        return torch.cat((token_ids, eos_tokens), dim=1), torch.cat((attention_mask, eos_mask), dim=1)

    def context_input_transform(self, context: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if context.shape[-1] > self.config.context_length:
            context = context[..., -self.config.context_length :]
        token_ids, attention_mask, scale = self._input_transform(context=context)
        if self.config.use_eos_token and self.config.model_type == "seq2seq":
            token_ids, attention_mask = self._append_eos_token(token_ids, attention_mask)
        return token_ids, attention_mask, scale

    def output_transform(self, samples: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
        centers = self.centers.to(device=samples.device)
        indices = torch.clamp(
            samples.long() - self.config.n_special_tokens - 1,
            min=0,
            max=len(centers) - 1,
        )
        scale_unsqueezed = scale.to(device=samples.device).unsqueeze(-1).unsqueeze(-1)
        return centers[indices] * scale_unsqueezed

    def token_to_value(self, token_id: int, scale: torch.Tensor | float = 1.0) -> float:
        if isinstance(scale, torch.Tensor):
            scale_value = float(scale.flatten()[0].detach().cpu())
        else:
            scale_value = float(scale)
        idx = int(token_id) - self.config.n_special_tokens - 1
        idx = max(0, min(idx, len(self.centers) - 1))
        return float(self.centers[idx].detach().cpu()) * scale_value


def create_tokenizer_from_config(config: ChronosConfigLite) -> MeanScaleUniformBinsLite:
    if config.tokenizer_class != "MeanScaleUniformBins":
        raise ValueError(
            f"Unsupported Chronos tokenizer_class={config.tokenizer_class!r}. "
            "This implementation currently supports MeanScaleUniformBins only."
        )
    return MeanScaleUniformBinsLite(config=config, **config.tokenizer_kwargs)


def load_chronos_t5_raw(
    model_id: str = DEFAULT_CHRONOS_MODEL_ID,
    device: str | torch.device | None = None,
    dtype: torch.dtype | str | None = None,
):
    """Load original Chronos v1 T5 with raw Hugging Face Transformers.

    Returns
    -------
    model, tokenizer, chronos_config
    """
    from transformers import AutoConfig, AutoModelForSeq2SeqLM

    hf_config = AutoConfig.from_pretrained(model_id)
    chronos_config = ChronosConfigLite.from_transformers_config(hf_config)
    if chronos_config.model_type != "seq2seq":
        raise ValueError("This raw implementation currently targets Chronos-T5 seq2seq checkpoints.")

    if dtype is not None and isinstance(dtype, str):
        dtype = getattr(torch, dtype)

    model_kwargs = {}
    if dtype is not None:
        model_kwargs["torch_dtype"] = dtype
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, **model_kwargs)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    tokenizer = create_tokenizer_from_config(chronos_config)
    return model, tokenizer, chronos_config


def prepare_chronos_context(x, device: str | torch.device | None = None) -> torch.Tensor:
    """Prepare a single univariate context for Chronos.

    Chronos uses NaN left-padding for unequal lengths. For one series we simply
    return shape [1, T].
    """
    context = torch.as_tensor(x.copy() if hasattr(x, "copy") else x, dtype=torch.float32).unsqueeze(0)
    if device is not None:
        context = context.to(device)
    return context

