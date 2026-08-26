# Sample Joey Structured Outputs

## Example 1

Parent note:

"He was anxious before school, refused breakfast, and had a meltdown when I asked him to put his jumper on."

Output produced by the deterministic extractor:

```json
{
  "entry_type": "journal_entry",
  "summary": "Morning entry; mood/signals: Anxious, Meltdown, Sensory discomfort; behaviours: meltdown, refusal; possible triggers: school transition or school-related demand, clothing or tactile discomfort.",
  "date": null,
  "time_of_day": "morning",
  "anxiety_level": "High",
  "mood_zone": "Red",
  "mood_labels": [
    "Anxious",
    "Meltdown",
    "Sensory discomfort"
  ],
  "behaviours": [
    "meltdown",
    "refusal"
  ],
  "activity": "school-related routine",
  "environment": "school",
  "possible_triggers": [
    "school transition or school-related demand",
    "clothing or tactile discomfort"
  ],
  "quick_track_suggestions": [
    "Anxiety",
    "Meltdown/Shutdown",
    "Appetite",
    "Meal Entry",
    "School Attendance",
    "Physical Discomfort"
  ],
  "strategy_categories": [
    "Behavioural Challenges & Emotional Regulation",
    "Eating & Mealtime Challenges",
    "School Success & Academic Collaboration",
    "Sensory Processing & Environmental Support"
  ],
  "risk_flags": [],
  "missing_information": [
    "reason for clothing discomfort"
  ],
  "follow_up_question": "Was the clothing uncomfortable because of the fabric, label, tightness, temperature, or something else?",
  "confidence": "Medium",
  "requires_parent_confirmation": true
}