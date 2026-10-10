"""PyTorch Transformer model for Remaining Useful Life (RUL) prediction."""
import logging
from typing import Tuple, List, Dict, Any
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd
import math

logger = logging.getLogger(__name__)


class PositionalEncoding(nn.Module):
    """Injects some information about the relative or absolute position of the tokens in the sequence."""
    
    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 5000):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor, shape [seq_len, batch_size, embedding_dim]
        """
        x = x + self.pe[:x.size(0)]
        return self.dropout(x)


class TransformerRUL(nn.Module):
    """Transformer Encoder architecture for sequence-to-value RUL prediction."""
    
    def __init__(self, n_features: int, d_model: int = 32, nhead: int = 4, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.n_features = n_features
        
        self.embedding = nn.Linear(n_features, d_model)
        self.pos_encoder = PositionalEncoding(d_model, dropout)
        
        encoder_layers = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward=d_model*2, dropout=dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers)
        
        self.regressor = nn.Sequential(
            nn.Linear(d_model, 16),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(16, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        x shape: (batch, seq_len, features)
        """
        # Embed and add positional encoding
        x = self.embedding(x)
        # Note: PyTorch TransformerEncoder with batch_first=True expects (batch, seq, feature)
        # But PositionalEncoding expects (seq, batch, feature)
        x = x.transpose(0, 1)
        x = self.pos_encoder(x)
        x = x.transpose(0, 1)
        
        # Transformer
        output = self.transformer_encoder(x)
        
        # Use the last token representation for sequence-level prediction
        last_token = output[:, -1, :]
        
        # Predict RUL
        rul = self.regressor(last_token)
        return rul.squeeze(-1)


def create_sequences_and_targets(df: pd.DataFrame, feature_cols: List[str], target_col: str, seq_length: int = 30) -> Tuple[torch.Tensor, torch.Tensor]:
    """Create rolling sequences and corresponding targets."""
    sequences = []
    targets = []
    
    for _, group in df.groupby("machine_id"):
        data = group[feature_cols].values
        target_data = group[target_col].values
        
        if len(data) < seq_length:
            continue
            
        for i in range(len(data) - seq_length + 1):
            sequences.append(data[i:(i + seq_length)])
            # The target is the RUL at the end of the sequence
            targets.append(target_data[i + seq_length - 1])
            
    if not sequences:
        return torch.tensor([]), torch.tensor([])
        
    return torch.tensor(np.array(sequences), dtype=torch.float32), torch.tensor(np.array(targets), dtype=torch.float32)


class TransformerRULModel:
    """Wrapper for the Transformer model."""
    
    def __init__(
        self, 
        n_features: int, 
        d_model: int = 32, 
        nhead: int = 4,
        num_layers: int = 2,
        learning_rate: float = 0.001,
        device: str = "cpu"
    ):
        self.n_features = n_features
        self.device = torch.device(device)
        self.model = TransformerRUL(n_features, d_model, nhead, num_layers).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()
        
    def fit(self, X: torch.Tensor, y: torch.Tensor, epochs: int = 20, batch_size: int = 32) -> "TransformerRULModel":
        """Train the model."""
        if len(X) == 0:
            logger.warning("Empty dataset for training")
            return self
            
        dataset = TensorDataset(X, y)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        self.model.train()
        
        for epoch in range(epochs):
            total_loss = 0
            for batch_x, batch_y in loader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)
                
                self.optimizer.zero_grad()
                preds = self.model(batch_x)
                loss = self.criterion(preds, batch_y)
                loss.backward()
                # Gradient clipping to prevent exploding gradients
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                
                total_loss += loss.item()
                
            avg_loss = total_loss / len(loader)
            if (epoch + 1) % 5 == 0:
                logger.info(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}")
                
        return self

    def predict(self, X: torch.Tensor) -> np.ndarray:
        """Predict RUL."""
        if len(X) == 0:
            return np.array([])
            
        self.model.eval()
        with torch.no_grad():
            preds = self.model(X.to(self.device))
            
        # RUL cannot be negative
        preds_np = preds.cpu().numpy()
        return np.maximum(preds_np, 0)
