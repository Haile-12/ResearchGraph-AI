import { MessageSquare, Trash2, ChevronRight } from 'lucide-react';
import { truncate, formatRelativeTime } from '../../utils/formatters';
export default function SessionItem({ session, isActive, onSelect, onDelete }) {
    return (
        <div
            className={`modern-session-item ${isActive ? 'active' : ''}`}
            onClick={() => onSelect(session.id)}
            id={`session-${session.id}`}
        >
            <div className="session-item-icon">
                <MessageSquare size={14} color={isActive ? 'white' : '#64748b'} />
            </div>
            <div className="session-item-content">
                <div className="session-item-title">
                    {session.name}
                </div>
                {session.lastQuery && (
                    <div className="session-item-desc">
                        {truncate(session.lastQuery, 40)}
                    </div>
                )}
            </div>
            <div className="session-item-actions">
                <span className="session-item-time">
                    {session.lastActivity ? formatRelativeTime(session.lastActivity) : ''}
                </span>
                <button
                    onClick={e => { e.stopPropagation(); onDelete(session.id); }}
                    className="session-delete-btn"
                    aria-label="Delete session"
                    id={`delete-session-${session.id}`}
                >
                    <Trash2 size={13} />
                </button>
            </div>
        </div>
    );
}
