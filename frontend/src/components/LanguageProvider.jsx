import { useCallback, useEffect, useMemo, useState } from 'react';
import { LanguageContext } from '../contexts/LanguageContext';
import { TRANSLATIONS } from '../data/translations';

const STORAGE_KEY = 'yz.language';

function readLanguage() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'fr' ? 'fr' : 'en';
  } catch {
    return 'en';
  }
}

function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(readLanguage);

  useEffect(() => {
    document.documentElement.lang = language;
    document.title =
      language === 'fr'
        ? 'YANN ZAKPA // DÉVELOPPEUR FULL-STACK & TECHNICIEN INFORMATIQUE'
        : 'YANN ZAKPA // FULL-STACK DEVELOPER & IT TECHNICIAN';
    try {
      window.localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // The selection remains active for this page load when storage is unavailable.
    }
  }, [language]);

  const toggleLanguage = useCallback(() => {
    setLanguage((current) => (current === 'en' ? 'fr' : 'en'));
  }, []);

  const translate = useCallback(
    (text) => (language === 'fr' ? TRANSLATIONS[text] ?? text : text),
    [language]
  );

  const value = useMemo(
    () => ({ language, toggleLanguage, translate }),
    [language, toggleLanguage, translate]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export default LanguageProvider;
