# Frontend
Contract v0.2. Plain HTML/CSS/ES modules.
Run `cd frontend`, `npm start`, then open http://localhost:5173/?mode=fixture.
Without explicit mode=fixture requests go to same-origin live Backend; errors never switch mode.
Fixture data is fictional and does not prove authentication, actual SSE, prices, routing, or Qwen.
`npm test` runs Node boundary checks. Python static server also works when installed.
Set the public Kakao JavaScript key in index.html meta[name="kakao-map-app-key"]; register localhost:5173 and the live origin in Kakao allowed Web domains. Do not put REST/API secret keys here.
Actual SDK and real provider checks are G4 handoff items.
