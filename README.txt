FUNNELANALYTICS WEBSITE - STEP 1

This is the first website shell built from the existing FunnelAnalytics project.

1. Keep these existing folders beside this website:
   data/
   models/

2. Install:
   pip install -r requirements.txt

3. Run:
   python app.py

4. Open:
   http://localhost:5000

The website reads:
- data/user_journey_data.csv
- data/user_journey.db
- models/dropout_model.pkl
- models/model_metrics.pkl

Live events refresh automatically every 2 seconds.

Next step:
- connect the complete existing live_user.py event flow,
- connect the full historical user-data table,
- connect the exact funnel calculations,
- add the AI recommendation engine.
