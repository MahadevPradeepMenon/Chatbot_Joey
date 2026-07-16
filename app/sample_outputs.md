# Sample Joey Structured Outputs

## Example 1

Parent note:

"He was anxious before school, refused breakfast, and had a meltdown when I asked him to put his jumper on."

Suggested structured output:

```json
{
  "entry_type": "journal_entry",
  "summary": "Anxious morning before school with breakfast refusal and meltdown during dressing.",
  "date": null,
  "time_of_day": "morning",
  "anxiety_level": "High",
  "mood_zone": "Mixed",
  "mood_labels": ["Anxious", "Frustrated", "Meltdown"],
  "behaviours": ["refused breakfast", "meltdown"],
  "activity": "getting ready for school",
  "environment": "home",
  "possible_triggers": ["school transition", "clothing discomfort", "morning routine"],
  "quick_track_suggestions": ["Anxiety", "Appetite", "Meltdown/Shutdown"],
  "strategy_categories": ["Emotional Regulation", "Sensory Processing", "School Transitions"],
  "risk_flags": [],
  "missing_information": ["reason for jumper distress"],
  "follow_up_question": "Was the jumper uncomfortable because of the fabric, label, tightness, temperature, or something else?",
  "confidence": "Medium",
  "requires_parent_confirmation": true
}