import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
import numpy as np
import pandas as pd
import ta
from sklearn.preprocessing import StandardScaler
from .lstm_model import PriceLSTM
import config

class AIStrategy:
    def __init__(self, symbol):
        self.symbol = symbol
        self.model = None
        self.scaler = StandardScaler()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def prepare_features(self, df: pd.DataFrame):
        """Generates technical indicators and normalizes data."""
        if df.empty:
            return None
            
        df = df.copy()
        
        # Technical Indicators
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        df['macd'] = ta.trend.macd_diff(df['close'])
        df['ema_20'] = ta.trend.ema_indicator(df['close'], window=20)
        
        # Target: 1 if next CLOSE is higher than current CLOSE, else 0
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        # Drop NaNs created by indicators
        df.dropna(inplace=True)
        
        # Select Features
        feature_cols = ['close', 'volume', 'rsi', 'macd', 'ema_20']
        
        # Scale Data
        scaled_data = self.scaler.fit_transform(df[feature_cols])
        
        return scaled_data, df['target'].values, feature_cols
        
    def create_sequences(self, data, target, seq_length):
        xs, ys = [], []
        for i in range(len(data) - seq_length):
            x = data[i:(i + seq_length)]
            y = target[i + seq_length] # predict the direction at step i+seq_length
            xs.append(x)
            ys.append(y)
        return np.array(xs), np.array(ys)

    def train(self, df: pd.DataFrame):
        print(f"Training AI model for {self.symbol}...")
        
        features, targets, feature_cols = self.prepare_features(df)
        if features is None or len(features) < config.SEQ_LENGTH + 10:
            print("Not enough data to train.")
            return False

        X, y = self.create_sequences(features, targets, config.SEQ_LENGTH)
        
        # Convert to Tensors
        X_train = torch.from_numpy(X).float().to(self.device)
        y_train = torch.from_numpy(y).float().to(self.device)
        
        # Initialize Model
        input_dim = len(feature_cols)
        self.model = PriceLSTM(input_dim, config.HIDDEN_DIM, config.NUM_LAYERS, config.OUTPUT_DIM).to(self.device)
        
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=config.LEARNING_RATE)
        
        # Create DataLoader for Mini-Batch Training
        dataset = TensorDataset(X_train, y_train)
        loader = DataLoader(dataset, batch_size=config.BATCH_SIZE, shuffle=True)
        
        # Training Loop
        self.model.train()
        for epoch in range(config.EPOCHS):
            epoch_loss = 0
            for batch_X, batch_y in loader:
                outputs = self.model(batch_X)
                loss = criterion(outputs.squeeze(1), batch_y.float())
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
            
            # Print average loss for the epoch
            if (epoch+1) % 5 == 0:
                avg_loss = epoch_loss / len(loader)
                print(f'Epoch [{epoch+1}/{config.EPOCHS}], Loss: {avg_loss:.4f}')
                
        return True

    def predict(self, recent_data: pd.DataFrame):
        """
        Takes the most recent raw dataframe (including enough history for seq_length),
        calculates features, and predicts the NEXT move.
        """
        if self.model is None:
            print("Model not trained yet.")
            return None
            
        # We need to process features exactly like training
        # Note: In real prod, we should fit scaler on training set and transform here.
        # For this Mini version, we re-fit on looking-back window which is acceptable for 'rolling' stats.
        features, _, _ = self.prepare_features(recent_data)
        
        # Get the LAST sequence
        last_sequence = features[-config.SEQ_LENGTH:]
        
        if len(last_sequence) < config.SEQ_LENGTH:
            print("Not enough recent data for prediction.")
            return None
            
        feature_tensor = torch.from_numpy(last_sequence).float().unsqueeze(0).to(self.device)
        
        self.model.eval()
        with torch.no_grad():
            prediction = self.model(feature_tensor)
            prob = prediction.item()
            
        print(f"Prediction for {self.symbol}: {prob:.4f}")
        return prob # Probability > 0.5 implies UP
