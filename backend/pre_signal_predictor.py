import time
from typing import Dict, Optional, Tuple
from collections import deque
from datetime import datetime

class PreSignalPredictor:
    """
    Predicts when trading signals will trigger based on price momentum,
    RSI trends, and EMA convergence. Sends early alerts 20-60 seconds
    before expected entry.
    """
    
    def __init__(self, signal_lead_time: int = 30):
        """
        Initialize predictor
        
        Args:
            signal_lead_time: Time in seconds to alert before signal (default 30s)
        """
        self.signal_lead_time = signal_lead_time
        self.price_history: Dict[str, deque] = {}
        self.rsi_history: Dict[str, deque] = {}
        self.ema_history: Dict[str, deque] = {}
        self.pre_signals_sent: Dict[str, Dict] = {}
        self.prediction_log = []
        
        # Keep last N data points for trend analysis
        self.history_size = 10
        
        # Confidence thresholds
        self.min_confidence_for_presignal = 0.90
        
    def add_data_point(self, symbol: str, price: float, rsi: float, ema12: float, ema26: float):
        """
        Add new data point to history for trend analysis
        
        Args:
            symbol: Trading pair
            price: Current price
            rsi: Current RSI value
            ema12: Current EMA12 value
            ema26: Current EMA26 value
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.history_size)
            self.rsi_history[symbol] = deque(maxlen=self.history_size)
            self.ema_history[symbol] = deque(maxlen=self.history_size)
            
        timestamp = time.time()
        
        self.price_history[symbol].append((timestamp, price))
        self.rsi_history[symbol].append((timestamp, rsi))
        self.ema_history[symbol].append((timestamp, (ema12, ema26)))
        
    def predict_signal(self, symbol: str, current_price: float, ema12: float, ema26: float, 
                      rsi: float, confidence: float) -> Optional[Dict]:
        """
        Predict if a signal is about to trigger in the next 20-60 seconds
        
        Args:
            symbol: Trading pair
            current_price: Current market price
            ema12: Current EMA12 value
            ema26: Current EMA26 value
            rsi: Current RSI value
            confidence: Current signal confidence (0-1)
            
        Returns:
            Pre-signal dict if prediction is made, None otherwise
        """
        # Skip if we don't have enough history
        if symbol not in self.price_history or len(self.price_history[symbol]) < 3:
            return None
            
        # Skip if confidence is below 90%
        if confidence < self.min_confidence_for_presignal:
            return None
            
        # Check if we already sent a pre-signal recently (avoid spam)
        if symbol in self.pre_signals_sent:
            last_presignal = self.pre_signals_sent[symbol]
            time_since_presignal = time.time() - last_presignal.get("sent_at", 0)
            
            # If we sent a pre-signal less than signal_lead_time ago, skip
            if time_since_presignal < self.signal_lead_time:
                return None
                
            # If same signal type was already sent, skip
            if last_presignal.get("predicted_signal") == self._determine_approaching_signal(ema12, ema26, rsi):
                if time_since_presignal < 120:  # Don't repeat same pre-signal within 2 minutes
                    return None
        
        # Analyze trends
        price_velocity = self._calculate_price_velocity(symbol)
        rsi_velocity = self._calculate_rsi_velocity(symbol)
        ema_convergence = self._calculate_ema_convergence(symbol)
        
        # Determine what signal is approaching
        approaching_signal = self._determine_approaching_signal(ema12, ema26, rsi)
        
        if not approaching_signal:
            return None
            
        # Estimate time to trigger
        estimated_time_to_trigger = self._estimate_time_to_trigger(
            approaching_signal, ema12, ema26, rsi, price_velocity, 
            rsi_velocity, ema_convergence
        )
        
        if not estimated_time_to_trigger:
            return None
            
        # Only send pre-signal if estimated time is within our lead time window (20-60 seconds)
        if self.signal_lead_time - 10 <= estimated_time_to_trigger <= self.signal_lead_time + 30:
            # Calculate expected entry price
            expected_entry = self._estimate_entry_price(
                current_price, price_velocity, estimated_time_to_trigger
            )
            
            # Build pre-signal data
            pre_signal = {
                "symbol": symbol,
                "predicted_signal": approaching_signal,
                "current_price": current_price,
                "expected_entry": expected_entry,
                "estimated_time_seconds": estimated_time_to_trigger,
                "confidence": confidence,
                "ema12": ema12,
                "ema26": ema26,
                "rsi": rsi,
                "price_velocity": price_velocity,
                "rsi_velocity": rsi_velocity,
                "ema_convergence": ema_convergence,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sent_at": time.time()
            }
            
            # Store that we sent this pre-signal
            self.pre_signals_sent[symbol] = pre_signal
            
            # Log the prediction for accuracy tracking
            self.prediction_log.append({
                **pre_signal,
                "actual_trigger_time": None,  # Will be filled when signal actually triggers
                "prediction_accuracy": None
            })
            
            return pre_signal
            
        return None
        
    def _calculate_price_velocity(self, symbol: str) -> float:
        """Calculate price change rate ($/second)"""
        history = self.price_history[symbol]
        
        if len(history) < 2:
            return 0.0
            
        # Calculate average velocity over last few data points
        velocities = []
        for i in range(1, len(history)):
            time_diff = history[i][0] - history[i-1][0]
            price_diff = history[i][1] - history[i-1][1]
            
            if time_diff > 0:
                velocity = price_diff / time_diff
                velocities.append(velocity)
                
        return sum(velocities) / len(velocities) if velocities else 0.0
        
    def _calculate_rsi_velocity(self, symbol: str) -> float:
        """Calculate RSI change rate (points/second)"""
        history = self.rsi_history[symbol]
        
        if len(history) < 2:
            return 0.0
            
        # Calculate average RSI velocity
        velocities = []
        for i in range(1, len(history)):
            time_diff = history[i][0] - history[i-1][0]
            rsi_diff = history[i][1] - history[i-1][1]
            
            if time_diff > 0:
                velocity = rsi_diff / time_diff
                velocities.append(velocity)
                
        return sum(velocities) / len(velocities) if velocities else 0.0
        
    def _calculate_ema_convergence(self, symbol: str) -> float:
        """Calculate how fast EMA12 and EMA26 are converging/diverging"""
        history = self.ema_history[symbol]
        
        if len(history) < 2:
            return 0.0
            
        # Calculate convergence rate
        convergences = []
        for i in range(1, len(history)):
            time_diff = history[i][0] - history[i-1][0]
            
            prev_spread = history[i-1][1][0] - history[i-1][1][1]  # EMA12 - EMA26
            curr_spread = history[i][1][0] - history[i][1][1]
            
            spread_change = curr_spread - prev_spread
            
            if time_diff > 0:
                convergence_rate = spread_change / time_diff
                convergences.append(convergence_rate)
                
        return sum(convergences) / len(convergences) if convergences else 0.0
        
    def _determine_approaching_signal(self, ema12: float, ema26: float, rsi: float) -> Optional[str]:
        """
        Determine if BUY or SELL signal is approaching
        
        BUY signal triggers when: EMA12 > EMA26 AND RSI > 50
        SELL signal triggers when: EMA12 < EMA26 AND RSI < 50
        """
        # Check if we're close to triggering a BUY
        # Case 1: EMA12 approaching EMA26 from below, RSI approaching 50 from below
        if ema12 < ema26 and rsi < 50:
            ema_gap_pct = abs(ema12 - ema26) / ema26 * 100
            rsi_gap = 50 - rsi
            
            # Close to BUY trigger if gaps are small
            if ema_gap_pct < 0.5 and rsi_gap < 5:  # Within 0.5% for EMA, within 5 points for RSI
                return "BUY"
                
        # Case 2: Already bullish EMA but RSI approaching 50 from below
        elif ema12 > ema26 and rsi < 50:
            rsi_gap = 50 - rsi
            if rsi_gap < 5:
                return "BUY"
                
        # Case 3: Already bullish RSI but EMA approaching crossover from below
        elif ema12 < ema26 and rsi > 50:
            ema_gap_pct = abs(ema12 - ema26) / ema26 * 100
            if ema_gap_pct < 0.5:
                return "BUY"
        
        # Check if we're close to triggering a SELL
        # Case 1: EMA12 approaching EMA26 from above, RSI approaching 50 from above
        if ema12 > ema26 and rsi > 50:
            ema_gap_pct = abs(ema12 - ema26) / ema26 * 100
            rsi_gap = rsi - 50
            
            # Close to SELL trigger if gaps are small
            if ema_gap_pct < 0.5 and rsi_gap < 5:
                return "SELL"
                
        # Case 2: Already bearish EMA but RSI approaching 50 from above
        elif ema12 < ema26 and rsi > 50:
            rsi_gap = rsi - 50
            if rsi_gap < 5:
                return "SELL"
                
        # Case 3: Already bearish RSI but EMA approaching crossover from above
        elif ema12 > ema26 and rsi < 50:
            ema_gap_pct = abs(ema12 - ema26) / ema26 * 100
            if ema_gap_pct < 0.5:
                return "SELL"
                
        return None
        
    def _estimate_time_to_trigger(self, signal_type: str, ema12: float, ema26: float, 
                                  rsi: float, price_velocity: float, rsi_velocity: float,
                                  ema_convergence: float) -> Optional[int]:
        """
        Estimate how many seconds until signal triggers
        
        Returns:
            Estimated seconds, or None if cannot estimate
        """
        estimates = []
        
        if signal_type == "BUY":
            # Estimate based on RSI approaching 50 from below
            if rsi < 50 and rsi_velocity > 0:
                rsi_gap = 50 - rsi
                time_to_rsi_trigger = rsi_gap / rsi_velocity
                estimates.append(time_to_rsi_trigger)
                
            # Estimate based on EMA12 approaching EMA26 from below
            if ema12 < ema26 and ema_convergence > 0:
                ema_gap = ema26 - ema12
                time_to_ema_trigger = ema_gap / ema_convergence
                estimates.append(time_to_ema_trigger)
                
        elif signal_type == "SELL":
            # Estimate based on RSI approaching 50 from above
            if rsi > 50 and rsi_velocity < 0:
                rsi_gap = rsi - 50
                time_to_rsi_trigger = rsi_gap / abs(rsi_velocity)
                estimates.append(time_to_rsi_trigger)
                
            # Estimate based on EMA12 approaching EMA26 from above
            if ema12 > ema26 and ema_convergence < 0:
                ema_gap = ema12 - ema26
                time_to_ema_trigger = ema_gap / abs(ema_convergence)
                estimates.append(time_to_ema_trigger)
                
        # Return average estimate if we have any
        if estimates:
            # Filter out unrealistic estimates (too fast or too slow)
            realistic_estimates = [e for e in estimates if 10 <= e <= 120]
            
            if realistic_estimates:
                return int(sum(realistic_estimates) / len(realistic_estimates))
                
        return None
        
    def _estimate_entry_price(self, current_price: float, price_velocity: float, 
                            time_to_trigger: int) -> float:
        """
        Estimate what the entry price will be when signal triggers
        
        Args:
            current_price: Current market price
            price_velocity: Price change rate ($/second)
            time_to_trigger: Estimated seconds to trigger
            
        Returns:
            Estimated entry price
        """
        # Simple linear projection
        price_change = price_velocity * time_to_trigger
        expected_price = current_price + price_change
        
        return round(expected_price, 2)
        
    def mark_signal_triggered(self, symbol: str, signal_type: str):
        """
        Mark that an actual signal was triggered - for accuracy tracking
        
        Args:
            symbol: Trading pair
            signal_type: BUY or SELL
        """
        if symbol in self.pre_signals_sent:
            pre_signal = self.pre_signals_sent[symbol]
            
            if pre_signal.get("predicted_signal") == signal_type:
                # Calculate how accurate our prediction was
                sent_at = pre_signal.get("sent_at", 0)
                actual_trigger_time = time.time()
                time_difference = actual_trigger_time - sent_at
                
                estimated_time = pre_signal.get("estimated_time_seconds", 0)
                accuracy_error = abs(time_difference - estimated_time)
                
                # Update prediction log
                for log_entry in reversed(self.prediction_log):
                    if (log_entry.get("symbol") == symbol and 
                        log_entry.get("predicted_signal") == signal_type and
                        log_entry.get("actual_trigger_time") is None):
                        
                        log_entry["actual_trigger_time"] = actual_trigger_time
                        log_entry["actual_seconds_to_trigger"] = time_difference
                        log_entry["prediction_accuracy"] = f"{accuracy_error:.1f}s error"
                        
                        print(f"📊 Pre-signal accuracy for {symbol}: Predicted {estimated_time}s, Actual {time_difference:.1f}s (Error: {accuracy_error:.1f}s)")
                        break
                        
    def get_prediction_stats(self) -> Dict:
        """Get statistics on prediction accuracy"""
        if not self.prediction_log:
            return {"total_predictions": 0, "triggered": 0, "accuracy": "N/A"}
            
        total = len(self.prediction_log)
        triggered = sum(1 for log in self.prediction_log if log.get("actual_trigger_time") is not None)
        
        # Calculate average error for triggered predictions
        errors = []
        for log in self.prediction_log:
            if log.get("actual_trigger_time") is not None:
                estimated = log.get("estimated_time_seconds", 0)
                actual = log.get("actual_seconds_to_trigger", 0)
                errors.append(abs(estimated - actual))
                
        avg_error = sum(errors) / len(errors) if errors else 0
        
        return {
            "total_predictions": total,
            "triggered": triggered,
            "not_triggered_yet": total - triggered,
            "trigger_rate": f"{triggered/total*100:.1f}%" if total > 0 else "0%",
            "average_error_seconds": f"{avg_error:.1f}s" if errors else "N/A"
        }
