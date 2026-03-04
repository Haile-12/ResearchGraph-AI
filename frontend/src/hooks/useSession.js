import { useState, useEffect, useCallback, useRef } from 'react';
import {
    createNewSession as apiCreateNewSession,
    listSessions as apiListSessions,
    deleteSession as apiDeleteSession,
    getSession as apiGetSession
} from '../services/api';
export function useSession() {
    const [sessions, setSessions] = useState([]);
    const [activeSessionId, setActiveSId] = useState(null);
    const hasInitialised = useRef(false);
    const fetchSessions = useCallback(async () => {
        try {
            const data = await apiListSessions();
            const formatted = data.sessions.map(s => ({
                id: s.session_id,
                name: s.title,
                updatedAt: s.updated_at,
                lastActivity: s.updated_at
            }));
            setSessions(formatted);
            if (formatted.length > 0 && !activeSessionId) {
                setActiveSId(formatted[0].id);
            }
            return formatted;
        } catch (err) {
            console.error("Failed to fetch sessions", err);
            return [];
        }
    }, [activeSessionId]);
    useEffect(() => {
        if (!hasInitialised.current) {
            fetchSessions();
            hasInitialised.current = true;
        }
    }, [fetchSessions]);
    const createNewSession = useCallback(async () => {
        try {
            const { session_id } = await apiCreateNewSession();
            setActiveSId(session_id);
            await fetchSessions();
            return session_id;
        } catch (err) {
            console.error("New session failed", err);
        }
    }, [fetchSessions]);
    const selectSession = useCallback((sessionId) => {
        setActiveSId(sessionId);
    }, []);
    const updateLastQuery = useCallback((sessionId, question) => {
        setSessions(prev =>
            prev.map(s => {
                if (s.id === sessionId) {
                    return { ...s, lastQuery: question };
                }
                return s;
            })
        );
    }, []);
    const deleteSession = useCallback(async (sessionId) => {
        try {
            await apiDeleteSession(sessionId);
            const refreshed = await fetchSessions();
            if (activeSessionId === sessionId) {
                if (refreshed.length > 0) {
                    setActiveSId(refreshed[0].id);
                } else {
                    await createNewSession();
                }
            }
        } catch (err) {
            console.error("Delete failed", err);
        }
    }, [activeSessionId, fetchSessions, createNewSession]);
    return {
        sessions,
        activeSessionId,
        createNewSession,
        selectSession,
        deleteSession,
        updateLastQuery,
        refreshSessions: fetchSessions
    };
}
