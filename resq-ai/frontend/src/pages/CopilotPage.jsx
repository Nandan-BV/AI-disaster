import React from 'react';
import { useAsyncData } from '../api/useAsyncData';
import Copilot from '../components/copilot/Copilot';

export default function CopilotPage() {
  const incidents = useAsyncData('/incidents');
  const list = incidents.data?.incidents || [];

  return (
    <div className="page">
      <Copilot incidents={list} />
    </div>
  );
}
