import { useState, useCallback, useRef, useEffect } from 'react';
import { sendQuery, getSession } from '../services/api';
let msgCounter = 0;
function newId() { return `msg-${++msgCounter}-${Date.now()}`; }
export function useChat(sessionId) {
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const lastPageRef = useRef(1);
    const loadSessionHistory = useCallback(async (sId) => {
        setIsLoading(true);
        try {
            const data = await getSession(sId);
            const history = data.history.map(m => ({
                id: m.id || Math.random().toString(36).substr(2, 9),
                role: m.role, 
                content: m.content,
                timestamp: m.timestamp || new Date().toISOString(),
                isHistory: true
            }));
            setMessages(history);
        } catch (err) {
            console.error("Failed to load history", err);
        } finally {
            setIsLoading(false);
        }
    }, []);
    useEffect(() => {
        if (!sessionId) {
            setMessages([]);
            return;
        }
        loadSessionHistory(sessionId);
    }, [sessionId, loadSessionHistory]);
    const appendMessages = useCallback((newMsgs) => {
        setMessages(prev => [...prev, ...newMsgs]);
    }, []);
    const sendMessage = useCallback(async (question, opts = {}, overrideSId = null) => {
        const sId = overrideSId || sessionId;
        if (!question.trim() || isLoading || !sId) return;
        setError(null);
        lastPageRef.current = 1;
        const userMsg = {
            id: newId(),
            role: 'user',
            content: question,
            timestamp: new Date(),
        };
        appendMessages([userMsg]);
        setIsLoading(true);
        try {
            const data = await sendQuery(question, sId, {
                page: 1,
                pageSize: opts.pageSize || 10,
                forceType: opts.forceType,
            });
            const assistantMsg = {
                id: newId(),
                role: 'assistant',
                content: data.answer,
                queryType: data.query_type,
                confidence: data.confidence_score,
                explanation: data.explanation,
                validation: data.validation,
                pagination: data.pagination,
                agentSteps: data.agent_steps || [],
                cached: data.cached,
                executionMs: data.execution_time_ms,
                timestamp: new Date(),
                originalQuestion: question,
            };
            appendMessages([assistantMsg]);
        } catch (err) {
            setError(err.message);
            appendMessages([{
                id: newId(),
                role: 'assistant',
                content: `❌ Error: ${err.message}`,
                queryType: 'ERROR',
                confidence: 0,
                timestamp: new Date(),
            }]);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId, isLoading, appendMessages]);
    const loadMore = useCallback(async (question, currentPage) => {
        if (isLoading) return;
        setIsLoading(true);
        const nextPage = currentPage + 1;
        try {
            const data = await sendQuery(question, sessionId, { page: nextPage });
            appendMessages([{
                id: newId(),
                role: 'assistant',
                content: data.answer,
                queryType: data.query_type,
                confidence: data.confidence_score,
                explanation: `Page ${nextPage} of results`,
                pagination: data.pagination,
                cached: data.cached,
                executionMs: data.execution_time_ms,
                timestamp: new Date(),
                originalQuestion: question,
                isPageResult: true,
                page: nextPage,
            }]);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId, isLoading, appendMessages]);
    const clearMessages = useCallback(() => {
        setMessages([]);
        setError(null);
        lastPageRef.current = 1;
    }, []);
    return {
        messages,
        isLoading,
        error,
        sendMessage,
        loadMore,
        clearMessages,
    };
}
