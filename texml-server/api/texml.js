export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/xml');
  res.status(200).send(`<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <AIAssistant id="assistant-6c04465e-3c71-4035-9ed3-a6943bbf3699">
        </AIAssistant>
    </Connect>
</Response>`);
}
