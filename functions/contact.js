export async function onRequestPost({ request, env }) {
  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    console.error("RESEND_API_KEY is not set in environment variables");
    return new Response("Configuration error", { status: 500 });
  }

  let formData;
  try {
    formData = await request.formData();
  } catch (error) {
    console.error("Failed to parse form data", error);
    return new Response("Invalid form submission", { status: 400 });
  }

  const name = (formData.get("name") || "").toString().trim();
  const email = (formData.get("email") || "").toString().trim();
  const message = (formData.get("message") || "").toString().trim();

  if (!name || !email || !message) {
    console.error("Missing required form fields", { namePresent: !!name, emailPresent: !!email, messagePresent: !!message });
    return new Response("Please provide name, email, and message.", { status: 400 });
  }

  const payload = {
    from: "Crux Energy Website <forms@cruxelectricalsystems.com>",
    to: ["projects@cruxelectricalsystems.com"],
    subject: "New contact form submission",
    text: `Name: ${name}\nEmail: ${email}\n\nMessage:\n${message}`,
  };

  try {
    const emailResponse = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(payload),
    });

    if (!emailResponse.ok) {
      const errorText = await emailResponse.text();
      console.error("Failed to send email via Resend", { status: emailResponse.status, body: errorText });
      return new Response("Unable to process your request right now.", { status: 502 });
    }
  } catch (error) {
    console.error("Error sending email via Resend", error);
    return new Response("Unable to process your request right now.", { status: 502 });
  }

  const thankYouUrl = new URL("/thank-you.html", request.url);
  return Response.redirect(thankYouUrl.toString(), 303);
}
