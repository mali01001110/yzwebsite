function Contact() {
  return (
    <section id="contact" className="page">
      <h1>Contact</h1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'center' }}>
        <p>
          <strong>Phone Number:</strong>{' '}
          <a href="tel:+2250709390845">+225 0709390845</a>
        </p>

        <p>
          <strong>Whatsapp Number:</strong>{' '}
          <a href="https://wa.me/2250778704523" target="_blank" rel="noopener noreferrer">+225 0778704523</a>
        </p>

        <p>
          <strong>Gmail Address:</strong>{' '}
          <a href="mailto:yannzakpa@gmail.com">yannzakpa@gmail.com</a>
        </p>
      </div>
    </section>
  );
}

export default Contact;
