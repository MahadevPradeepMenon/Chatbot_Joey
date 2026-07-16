# Manual Extractor Tests

## Test 1

Input:

"He was anxious before school, refused breakfast, and had a meltdown when I asked him to put his jumper on."

Expected:

- Anxiety detected
- School transition detected
- Food/appetite detected
- Meltdown detected
- Clothing discomfort detected
- Follow-up question about jumper/clothing

---

## Test 2

Input:

"She slept badly last night and was very tired this morning. She became upset when getting ready for school."

Expected:

- Sleep detected
- Energy level detected
- Mood zone Blue or Orange
- School routine detected
- Follow-up question about whether anxiety was present

---

## Test 3

Input:

"He banged his head during a meltdown and I was worried he might hurt himself."

Expected:

- Safety concern detected
- Self-injury mentioned
- Mood zone Red
- Anxiety Severe
- Crisis Management & Safety strategy category
- Follow-up question asking if the child is safe now