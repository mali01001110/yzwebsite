function SocialMediaProfiles() {
  // ️ Replace the URLs with your actual profile links
  const intro = `
    Find me online! Feel free to connect or follow me on any of the
    platforms listed below.
  `;

  const profiles = [
    {
      name: 'LinkedIn',
      url: 'https://www.linkedin.com/in/mali01001110/',
      description: 'Connect with me professionally',
    },
    {
      name: 'Facebook',
      url: 'https://www.facebook.com/profile.php?id=61586600751798',
      description: 'Follow my Facebook page',
    },
    {
      name: 'TikTok',
      url: 'https://www.tiktok.com/@sometaware?is_from_webapp=1&sender_device=pc',
      description: 'Check out my TikTok videos',
    },
  ];

  return (
    <section className="page">
      <h1>Social Media Profiles</h1>
      <p>{intro}</p>
      <ul className="social-list">
        {profiles.map((profile, idx) => (
          <li key={idx}>
            <a href={profile.url} target="_blank" rel="noopener noreferrer">
              <strong>{profile.name}</strong> — {profile.description}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default SocialMediaProfiles;
