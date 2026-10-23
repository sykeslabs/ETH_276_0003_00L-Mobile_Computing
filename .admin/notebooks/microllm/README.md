# MicroLLM helpers

The active course notebook is [05.18 Build Your Own Model](../../../02_Notebooks/05_Mobile_AI/05.18_Build_Your_Own_Model.ipynb). Its setup cell finds this folder automatically from the notebook folder or the repository root. Keep this directory when copying or cloning the course repository.

- `micro_llm_helpers.py` contains the model, training, visualizations, and completion widget.
- `micro_llm_training_data.py` supplies the example training sentences.
- `minifacts_qkv_inspector.py` is a standalone attention checkpoint inspector that requires separately exported model checkpoints.

Saved model files are written to the kernel's working directory.
