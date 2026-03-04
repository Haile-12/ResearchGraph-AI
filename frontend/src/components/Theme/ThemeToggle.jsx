import React from 'react';
import { Sun, Moon, Sparkles } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';
export default function ThemeToggle({ iconOnly = false }) {
    const { theme, toggleTheme } = useTheme();
    const getIcon = () => {
        return theme === 'light' ?
            <Sun size={iconOnly ? 16 : 18} /> :
            <Sparkles size={iconOnly ? 16 : 18} />;
    };
    const getLabel = () => {
        return theme === 'light' ? 'Light' : 'Night';
    };
    return (
        <button
            className={`theme-toggle ${iconOnly ? 'icon-only' : ''}`}
            onClick={toggleTheme}
            title={`Switch to ${theme === 'light' ? 'Night' : 'Light'} Mode`}
            aria-label="Toggle theme"
        >
            <div className="theme-toggle-content">
                {getIcon()}
                {!iconOnly && <span className="theme-toggle-label">{getLabel()} Mode</span>}
            </div>
        </button>
    );
}
