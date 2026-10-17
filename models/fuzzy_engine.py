# models/fuzzy_engine.py
# Mamdani Fuzzy Inference System for return decision making (Exp 6)
# Uses scikit-fuzzy to combine CNN confidence, Autoencoder anomaly score,
# and Customer Risk score into a final return decision.

import numpy as np

try:
    import skfuzzy as fuzz
    from skfuzzy import control as ctrl
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("[FuzzyEngine] scikit-fuzzy not available. Using fallback logic.")


class FuzzyDecisionEngine:
    """
    Mamdani Fuzzy Inference System.

    Inputs (all on universe 0-10):
      - anomaly_score   : from Autoencoder (0=normal, 10=highly anomalous)
      - cnn_confidence  : CNN confidence mapped (0=unconfident, 10=very confident)
      - customer_risk   : from risk scorer (0=low risk, 10=high risk)

    Output (0-10):
      - refund_decision : 0-3 = instant_refund, 3-6 = manual_audit, 6-10 = rejected

    Rules (Mamdani):
      R1: IF anomaly LOW   AND confidence HIGH AND risk LOW    → INSTANT_REFUND
      R2: IF anomaly LOW   AND confidence HIGH AND risk MEDIUM → INSTANT_REFUND
      R3: IF anomaly LOW   AND confidence LOW                  → MANUAL_AUDIT
      R4: IF anomaly MEDIUM                                    → MANUAL_AUDIT
      R5: IF confidence MEDIUM AND risk MEDIUM                 → MANUAL_AUDIT
      R6: IF anomaly HIGH                                      → REJECTED
      R7: IF risk HIGH                                         → REJECTED
      R8: IF confidence LOW  AND risk HIGH                     → REJECTED
      R9: IF anomaly LOW   AND confidence HIGH AND risk HIGH   → MANUAL_AUDIT
    """

    def __init__(self):
        self._system = None
        self._sim = None
        if FUZZY_AVAILABLE:
            self._build()

    def _build(self):
        # ── Universe variables ──
        anomaly    = ctrl.Antecedent(np.arange(0, 10.1, 0.1), 'anomaly_score')
        confidence = ctrl.Antecedent(np.arange(0, 10.1, 0.1), 'cnn_confidence')
        risk       = ctrl.Antecedent(np.arange(0, 10.1, 0.1), 'customer_risk')
        decision   = ctrl.Consequent(np.arange(0, 10.1, 0.1), 'refund_decision')

        # ── Membership functions ──
        anomaly['low']    = fuzz.trapmf(anomaly.universe,    [0, 0, 2, 4])
        anomaly['medium'] = fuzz.trimf(anomaly.universe,     [2, 5, 8])
        anomaly['high']   = fuzz.trapmf(anomaly.universe,    [6, 8, 10, 10])

        confidence['low']    = fuzz.trapmf(confidence.universe, [0, 0, 2, 4])
        confidence['medium'] = fuzz.trimf(confidence.universe,  [2, 5, 8])
        confidence['high']   = fuzz.trapmf(confidence.universe, [6, 8, 10, 10])

        risk['low']    = fuzz.trapmf(risk.universe, [0, 0, 2, 4])
        risk['medium'] = fuzz.trimf(risk.universe,  [2, 5, 8])
        risk['high']   = fuzz.trapmf(risk.universe, [6, 8, 10, 10])

        decision['instant_refund'] = fuzz.trapmf(decision.universe, [0, 0, 2, 4])
        decision['manual_audit']   = fuzz.trimf(decision.universe,  [2, 5, 8])
        decision['rejected']       = fuzz.trapmf(decision.universe, [6, 8, 10, 10])

        # ── Rules ──
        rules = [
            ctrl.Rule(anomaly['low'] & confidence['high'] & risk['low'],    decision['instant_refund']),
            ctrl.Rule(anomaly['low'] & confidence['high'] & risk['medium'], decision['instant_refund']),
            ctrl.Rule(anomaly['low'] & confidence['low'],                   decision['manual_audit']),
            ctrl.Rule(anomaly['medium'],                                     decision['manual_audit']),
            ctrl.Rule(confidence['medium'] & risk['medium'],                decision['manual_audit']),
            ctrl.Rule(anomaly['high'],                                       decision['rejected']),
            ctrl.Rule(risk['high'],                                          decision['rejected']),
            ctrl.Rule(confidence['low'] & risk['high'],                     decision['rejected']),
            ctrl.Rule(anomaly['low'] & confidence['high'] & risk['high'],   decision['manual_audit']),
        ]

        self._system = ctrl.ControlSystem(rules)
        self._sim = ctrl.ControlSystemSimulation(self._system)
        print("[FuzzyEngine] Mamdani FIS initialized with 9 rules.")

    def decide(self, anomaly_score: float, cnn_confidence: float, customer_risk: float) -> dict:
        """
        Run fuzzy inference and return the decision.

        Args:
            anomaly_score:   0-10 (from Autoencoder)
            cnn_confidence:  0-10 (CNN confidence * 10)
            customer_risk:   0-10 (from risk scorer)

        Returns:
            dict with decision label and output score
        """
        # Clamp inputs to valid universe range
        a = float(max(0.0, min(10.0, anomaly_score)))
        c = float(max(0.0, min(10.0, cnn_confidence)))
        r = float(max(0.0, min(10.0, customer_risk)))

        if FUZZY_AVAILABLE and self._sim is not None:
            try:
                self._sim.input['anomaly_score'] = a
                self._sim.input['cnn_confidence'] = c
                self._sim.input['customer_risk'] = r
                self._sim.compute()
                output = float(self._sim.output['refund_decision'])
            except Exception as e:
                print(f"[FuzzyEngine] Inference error: {e}. Using fallback.")
                output = self._fallback(a, c, r)
        else:
            output = self._fallback(a, c, r)

        # Map output score to decision label
        if output <= 3.5:
            label = "instant_refund"
            emoji = "✅"
        elif output <= 6.5:
            label = "manual_audit"
            emoji = "⚠️"
        else:
            label = "rejected"
            emoji = "❌"

        explanation = self._explain(label, a, c, r)

        return {
            "anomaly_input": round(a, 2),
            "confidence_input": round(c, 2),
            "risk_input": round(r, 2),
            "decision_score": round(output, 3),
            "decision": label,
            "emoji": emoji,
            "explanation": explanation,
        }

    def _fallback(self, a: float, c: float, r: float) -> float:
        """Simple rule-based fallback when scikit-fuzzy is unavailable."""
        if a >= 6 or r >= 7:
            return 8.0  # rejected
        elif a <= 3 and c >= 7 and r <= 4:
            return 1.5  # instant refund
        else:
            return 5.0  # manual audit

    def _explain(self, decision: str, a: float, c: float, r: float) -> str:
        """Generate a human-readable explanation for the decision."""
        explanations = {
            "instant_refund": (
                f"Product analysis shows low anomaly score ({a:.1f}/10), "
                f"high CNN confidence ({c:.1f}/10), and low account risk ({r:.1f}/10). "
                f"All indicators are within acceptable parameters for an automatic refund."
            ),
            "manual_audit": (
                f"Mixed signals detected — anomaly score: {a:.1f}/10, "
                f"CNN confidence: {c:.1f}/10, risk score: {r:.1f}/10. "
                f"A human quality specialist will review this case within 24-48 hours."
            ),
            "rejected": (
                f"High-risk indicators detected — anomaly score: {a:.1f}/10, "
                f"CNN confidence: {c:.1f}/10, risk score: {r:.1f}/10. "
                f"The product does not meet the return eligibility criteria. "
                f"Please contact support for further assistance."
            ),
        }
        return explanations.get(decision, "Decision computed by AI pipeline.")


# Singleton
_fuzzy_instance = None


def get_fuzzy_engine() -> FuzzyDecisionEngine:
    global _fuzzy_instance
    if _fuzzy_instance is None:
        _fuzzy_instance = FuzzyDecisionEngine()
    return _fuzzy_instance
