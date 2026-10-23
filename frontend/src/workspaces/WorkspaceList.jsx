function WorkspaceList({ workspaces, selectedId, onSelect }) {
    return (
        <ul>
            {workspaces.map((workspace) => (
                <li key={workspace.id}>
                    <button type='button' onClick={() => onSelect(workspace.id)}>
                        {workspace.name}
                        {workspace.id === selectedId && ' - выбрано'}
                    </button>
                </li>
            ))}
        </ul>
    )
}

export default WorkspaceList;