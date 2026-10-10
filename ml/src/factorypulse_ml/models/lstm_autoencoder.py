"""PyTorch LSTM Autoencoder for Anomaly Detection."""
import logging
from typing import Tuple, List, Dict
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd

logger = logging.getLogger(__name__)


class LSTMAutoencoder(nn.Module):
    """LSTM Autoencoder architecture."""
    
    def __init__(self, n_features: int, hidden_dim: int = 64, latent_dim: int = 16, num_layers: int = 1):
        super().__init__()
        self.n_features = n_features
        
        # Encoder
        self.encoder_lstm = nn.LSTM(
            input_size=n_features, 
            hidden_size=hidden_dim, 
            num_layers=num_layers, 
            batch_first=True
        )
        self.encoder_linear = nn.Linear(hidden_dim, latent_dim)
        
        # Decoder
        self.decoder_linear = nn.Linear(latent_dim, hidden_dim)
        self.decoder_lstm = nn.LSTM(
            input_size=hidden_dim, 
            hidden_size=n_features, 
            num_layers=num_layers, 
            batch_first=True
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        x shape: (batch, seq_len, features)
        """
        seq_len = x.shape[1]
        
        # Encode
        _, (hidden, _) = self.encoder_lstm(x)
        # hidden shape: (num_layers, batch, hidden_dim)
        # Take the last layer's hidden state
        encoded = self.encoder_linear(hidden[-1])
        
        # Decode
        decoded_hidden = self.decoder_linear(encoded)
        # Repeat the hidden state for each time step
        decoded_hidden = decoded_hidden.unsqueeze(1).repeat(1, seq_len, 1)
        
        reconstructed, _ = self.decoder_lstm(decoded_hidden)
        
        return reconstructed


def create_sequences(df: pd.DataFrame, feature_cols: List[str], seq_length: int = 30) -> torch.Tensor:
    """Create rolling sequences from a dataframe for time-series modeling."""
    sequences = []
    
    for _, group in df.groupby("machine_id"):
        data = group[feature_cols].values
        if len(data) < seq_length:
            continue
            
        for i in range(len(data) - seq_length + 1):
            sequences.append(data[i:(i + seq_length)])
            
    if not sequences:
        return torch.tensor([])
        
    return torch.tensor(np.array(sequences), dtype=torch.float32)


class AnomalyDetector:
    """Wrapper for the LSTM Autoencoder to handle training and scoring."""
    
    def __init__(
        self, 
        n_features: int, 
        seq_length: int = 30,
        hidden_dim: int = 64, 
        latent_dim: int = 16,
        learning_rate: float = 0.001,
        device: str = "cpu"
    ):
        self.n_features = n_features
        self.seq_length = seq_length
        self.device = torch.device(device)
        self.model = LSTMAutoencoder(n_features, hidden_dim, latent_dim).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()
        self.threshold = 0.0
        self.feature_names = []

    def fit(self, X: torch.Tensor, epochs: int = 20, batch_size: int = 32) -> "AnomalyDetector":
        """Train the autoencoder."""
        if len(X) == 0:
            logger.warning("Empty dataset for training")
            return self
            
        dataset = TensorDataset(X, X)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        self.model.train()
        
        for epoch in range(epochs):
            total_loss = 0
            for batch_x, _ in loader:
                batch_x = batch_x.to(self.device)
                
                self.optimizer.zero_grad()
                reconstructed = self.model(batch_x)
                loss = self.criterion(reconstructed, batch_x)
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
                
            avg_loss = total_loss / len(loader)
            if (epoch + 1) % 5 == 0:
                logger.info(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}")
                
        # Calculate threshold based on training reconstruction error
        self.model.eval()
        with torch.no_grad():
            train_reconstructed = self.model(X.to(self.device))
            # Calculate MSE per sequence
            mse = torch.mean((X.to(self.device) - train_reconstructed) ** 2, dim=[1, 2])
            # Set threshold at 99th percentile of training error
            self.threshold = float(torch.quantile(mse, 0.99).item())
            
        logger.info(f"Training completed. Anomaly threshold set to {self.threshold:.4f}")
        return self

    def predict_score(self, X: torch.Tensor) -> np.ndarray:
        """Calculate anomaly scores (reconstruction MSE)."""
        if len(X) == 0:
            return np.array([])
            
        self.model.eval()
        with torch.no_grad():
            X_tensor = X.to(self.device)
            reconstructed = self.model(X_tensor)
            # Calculate MSE per sequence
            mse = torch.mean((X_tensor - reconstructed) ** 2, dim=[1, 2])
            
        return mse.cpu().numpy()
        
    def predict(self, X: torch.Tensor) -> np.ndarray:
        """Predict binary anomaly (1 = anomaly, 0 = normal)."""
        scores = self.predict_score(X)
        return (scores > self.threshold).astype(int)
